"""Dashboard API endpoint."""

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_or_default
from app.api.schemas import (
    ActivityItem,
    CourseDueCount,
    CourseListItem,
    DashboardExamSummary,
    DashboardGamificationSummary,
    DashboardResponse,
    DashboardStreakInfo,
    DashboardStudyStats,
    UpcomingDeadlineItem,
)
from app.core.cache import DASHBOARD_TTL_SECONDS, cache_get, cache_set, dashboard_cache_key
from app.core.database import get_session
from app.models.user import User
from app.services import (
    achievement_service,
    challenge_service,
    course_service,
    courseops_service,
    exam_service,
    pipeline_service,
    review_service,
    srs_service,
    streak_service,
    xp_service,
)

logger = structlog.get_logger()

router = APIRouter()


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Get dashboard data",
    description="Returns pending review count, recent pipeline activity, course list with aggregate stats, and study statistics.",
)
async def get_dashboard(
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> DashboardResponse:
    """Get dashboard data: pending reviews, recent activity, courses, study stats."""
    # Check cache first
    cache_key = dashboard_cache_key(str(user.id))
    cached = await cache_get(cache_key)
    if cached is not None:
        return DashboardResponse(**cached)

    pending_count = await review_service.count_pending_reviews(session, user_id=user.id)
    activity_raw = await pipeline_service.get_recent_activity(session, limit=10, user_id=user.id)
    course_stats = await course_service.list_courses_with_stats(session, user_id=user.id)

    course_items = [CourseListItem(**cs) for cs in course_stats]
    activity = [ActivityItem(**item) for item in activity_raw]

    # Study stats (best-effort, don't break dashboard on failure)
    study_stats = None
    try:
        global_stats = await srs_service.get_global_study_stats(session, user_id=user.id)
        per_course = await srs_service.get_per_course_due_counts(session, user_id=user.id)
        study_stats = DashboardStudyStats(
            total=global_stats.total,
            due_today=global_stats.due_today,
            mastered=global_stats.mastered,
            learning=global_stats.learning,
            new=global_stats.new,
            per_course=[CourseDueCount(**pc) for pc in per_course],
        )
    except Exception:
        logger.warning("study_stats_failed", exc_info=True)

    # Active exams (best-effort)
    active_exams = []
    try:
        exams = await exam_service.list_exams(session, status="active", user_id=user.id)
        # Need course codes — build a lookup from course_items
        course_lookup = {c.id: c.code for c in course_items}
        for exam in exams:
            from datetime import datetime

            days_remaining = max(0, (exam.exam_date - datetime.utcnow()).days)
            active_exams.append(
                DashboardExamSummary(
                    exam_id=exam.id,
                    title=exam.title,
                    course_id=exam.course_id,
                    course_code=course_lookup.get(exam.course_id, ""),
                    exam_date=exam.exam_date.isoformat(),
                    days_remaining=days_remaining,
                    mastery_pct=0,  # lightweight — full progress via exam detail
                    target_mastery_pct=exam.target_mastery_pct,
                )
            )
    except Exception:
        logger.warning("active_exams_failed", exc_info=True)

    # Streak (best-effort)
    streak = None
    try:
        streak_data = await streak_service.get_streak(session, user_id=user.id)
        streak = DashboardStreakInfo(**streak_data)
    except Exception:
        logger.warning("streak_failed", exc_info=True)

    # Upcoming deadlines (best-effort)
    upcoming_deadlines = []
    try:
        raw_deadlines = await courseops_service.get_upcoming_deadlines_all_courses(
            session, limit=5, user_id=user.id
        )
        upcoming_deadlines = [UpcomingDeadlineItem(**d) for d in raw_deadlines]
    except Exception:
        logger.warning("upcoming_deadlines_failed", exc_info=True)

    # Gamification summary (best-effort)
    gamification = None
    try:
        xp_data = await xp_service.get_xp_summary(session, user.id)
        challenge_data = await challenge_service.get_user_challenge_progress(session, user.id)
        unnotified = await achievement_service.get_unnotified(session, user.id)
        gamification = DashboardGamificationSummary(
            total_xp=xp_data["total_xp"],
            level=xp_data["level"],
            progress_pct=xp_data["progress_pct"],
            next_threshold=xp_data["next_threshold"],
            daily_challenge_description=challenge_data["description"],
            daily_challenge_progress=challenge_data["progress"],
            daily_challenge_target=challenge_data["target"],
            daily_challenge_completed=challenge_data["completed"],
            unnotified_achievement_count=len(unnotified),
        )
    except Exception:
        logger.warning("gamification_failed", exc_info=True)

    response = DashboardResponse(
        pending_review_count=pending_count,
        recent_activity=activity,
        courses=course_items,
        study_stats=study_stats,
        active_exams=active_exams,
        streak=streak,
        upcoming_deadlines=upcoming_deadlines,
        gamification=gamification,
    )

    # Cache the response (best-effort)
    await cache_set(cache_key, response.model_dump(mode="json"), ttl=DASHBOARD_TTL_SECONDS)

    return response

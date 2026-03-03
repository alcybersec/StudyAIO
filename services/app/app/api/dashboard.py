"""Dashboard API endpoint."""

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    ActivityItem,
    CourseDueCount,
    CourseListItem,
    DashboardExamSummary,
    DashboardResponse,
    DashboardStreakInfo,
    DashboardStudyStats,
    UpcomingDeadlineItem,
)
from app.core.database import get_session
from app.services import course_service, courseops_service, exam_service, pipeline_service, review_service, srs_service, streak_service

logger = structlog.get_logger()

router = APIRouter()


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Get dashboard data",
    description="Returns pending review count, recent pipeline activity, course list with aggregate stats, and study statistics.",
)
async def get_dashboard(
    session: AsyncSession = Depends(get_session),
) -> DashboardResponse:
    """Get dashboard data: pending reviews, recent activity, courses, study stats."""
    pending_count = await review_service.count_pending_reviews(session)
    activity_raw = await pipeline_service.get_recent_activity(session, limit=10)
    course_stats = await course_service.list_courses_with_stats(session)

    course_items = [CourseListItem(**cs) for cs in course_stats]
    activity = [ActivityItem(**item) for item in activity_raw]

    # Study stats (best-effort, don't break dashboard on failure)
    study_stats = None
    try:
        global_stats = await srs_service.get_global_study_stats(session)
        per_course = await srs_service.get_per_course_due_counts(session)
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
        exams = await exam_service.list_exams(session, status="active")
        # Need course codes — build a lookup from course_items
        course_lookup = {c.id: c.code for c in course_items}
        for exam in exams:
            from datetime import datetime
            days_remaining = max(0, (exam.exam_date - datetime.utcnow()).days)
            active_exams.append(DashboardExamSummary(
                exam_id=exam.id,
                title=exam.title,
                course_id=exam.course_id,
                course_code=course_lookup.get(exam.course_id, ""),
                exam_date=exam.exam_date.isoformat(),
                days_remaining=days_remaining,
                mastery_pct=0,  # lightweight — full progress via exam detail
                target_mastery_pct=exam.target_mastery_pct,
            ))
    except Exception:
        logger.warning("active_exams_failed", exc_info=True)

    # Streak (best-effort)
    streak = None
    try:
        streak_data = await streak_service.get_streak(session)
        streak = DashboardStreakInfo(**streak_data)
    except Exception:
        logger.warning("streak_failed", exc_info=True)

    # Upcoming deadlines (best-effort)
    upcoming_deadlines = []
    try:
        raw_deadlines = await courseops_service.get_upcoming_deadlines_all_courses(session, limit=5)
        upcoming_deadlines = [UpcomingDeadlineItem(**d) for d in raw_deadlines]
    except Exception:
        logger.warning("upcoming_deadlines_failed", exc_info=True)

    return DashboardResponse(
        pending_review_count=pending_count,
        recent_activity=activity,
        courses=course_items,
        study_stats=study_stats,
        active_exams=active_exams,
        streak=streak,
        upcoming_deadlines=upcoming_deadlines,
    )

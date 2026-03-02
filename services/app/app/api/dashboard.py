"""Dashboard API endpoint."""

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    ActivityItem,
    CourseDueCount,
    CourseListItem,
    DashboardResponse,
    DashboardStudyStats,
)
from app.core.database import get_session
from app.services import course_service, pipeline_service, review_service, srs_service

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

    return DashboardResponse(
        pending_review_count=pending_count,
        recent_activity=activity,
        courses=course_items,
        study_stats=study_stats,
    )

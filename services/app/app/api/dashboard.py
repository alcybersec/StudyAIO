"""Dashboard API endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import ActivityItem, CourseListItem, DashboardResponse
from app.core.database import get_session
from app.services import course_service, pipeline_service, review_service

router = APIRouter()


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Get dashboard data",
    description="Returns pending review count, recent pipeline activity, and course list with aggregate stats.",
)
async def get_dashboard(
    session: AsyncSession = Depends(get_session),
) -> DashboardResponse:
    """Get dashboard data: pending reviews, recent activity, courses."""
    pending_count = await review_service.count_pending_reviews(session)
    activity_raw = await pipeline_service.get_recent_activity(session, limit=10)
    course_stats = await course_service.list_courses_with_stats(session)

    course_items = [CourseListItem(**cs) for cs in course_stats]
    activity = [ActivityItem(**item) for item in activity_raw]

    return DashboardResponse(
        pending_review_count=pending_count,
        recent_activity=activity,
        courses=course_items,
    )

"""Dashboard API endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import ActivityItem, CourseListItem, DashboardResponse
from app.core.database import get_session
from app.services import course_service, pipeline_service, review_service

router = APIRouter()


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    session: AsyncSession = Depends(get_session),
) -> DashboardResponse:
    """Get dashboard data: pending reviews, recent activity, courses."""
    pending_count = await review_service.count_pending_reviews(session)
    activity_raw = await pipeline_service.get_recent_activity(session, limit=10)
    courses = await course_service.list_courses(session)

    # Build course list items with aggregate data
    course_items = []
    for c in courses:
        weeks = await course_service.get_course_weeks(session, c.id)
        course_items.append(
            CourseListItem(
                id=c.id,
                code=c.code,
                name=c.name,
                term=c.term,
                created_at=c.created_at,
                updated_at=c.updated_at,
                weeks_covered=len(weeks),
                total_artifacts=sum(w["artifact_count"] for w in weeks),
                last_updated=c.updated_at,
            )
        )

    activity = [ActivityItem(**item) for item in activity_raw]

    return DashboardResponse(
        pending_review_count=pending_count,
        recent_activity=activity,
        courses=course_items,
    )

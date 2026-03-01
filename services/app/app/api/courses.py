"""Course API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    ArtifactResponse,
    CourseDetailResponse,
    CourseListItem,
    CourseResponse,
    SummaryResponse,
    WeekDetailResponse,
    WeekSummaryRow,
)
from app.core.database import get_session
from app.services import artifact_service, course_service, summary_service

router = APIRouter()


@router.get(
    "/courses",
    response_model=list[CourseListItem],
    summary="List all courses",
    description="Returns all courses with aggregate stats: weeks covered, total artifacts, last updated.",
)
async def list_courses(
    session: AsyncSession = Depends(get_session),
) -> list[CourseListItem]:
    """List all courses with aggregate stats."""
    course_stats = await course_service.list_courses_with_stats(session)
    return [CourseListItem(**cs) for cs in course_stats]


@router.get(
    "/courses/{course_code}",
    response_model=CourseDetailResponse,
    summary="Get course detail",
    description="Returns course info with per-week breakdown including artifact counts, summary status, and asset counts.",
)
async def get_course_detail(
    course_code: str,
    session: AsyncSession = Depends(get_session),
) -> CourseDetailResponse:
    """Get course detail with per-week breakdown."""
    course = await course_service.get_course_by_code(session, course_code)
    if not course:
        raise HTTPException(status_code=404, detail=f"Course {course_code} not found")

    weeks_data = await course_service.get_course_weeks(session, course.id)
    weeks = [WeekSummaryRow(**w) for w in weeks_data]

    return CourseDetailResponse(
        course=CourseResponse.model_validate(course),
        weeks=weeks,
    )


@router.get(
    "/courses/{course_code}/weeks/{week}",
    response_model=WeekDetailResponse,
    summary="Get week detail",
    description="Returns full detail for a specific course week: course info, summary (if generated), and artifact list.",
)
async def get_week_detail(
    course_code: str,
    week: int,
    session: AsyncSession = Depends(get_session),
) -> WeekDetailResponse:
    """Get full detail for a specific course week."""
    course = await course_service.get_course_by_code(session, course_code)
    if not course:
        raise HTTPException(status_code=404, detail=f"Course {course_code} not found")

    artifacts = await artifact_service.list_artifacts(session, course_id=course.id, week=week)
    summary = await summary_service.get_summary_for_week(session, course_code, week)

    return WeekDetailResponse(
        course=CourseResponse.model_validate(course),
        week=week,
        summary=SummaryResponse.model_validate(summary) if summary else None,
        artifacts=[ArtifactResponse.model_validate(a) for a in artifacts],
    )

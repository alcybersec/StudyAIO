"""Course API endpoints."""

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_or_default
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
from app.models.user import User
from app.services import artifact_service, course_service, summary_service

logger = structlog.get_logger()

router = APIRouter()


class CourseUpdateRequest(BaseModel):
    """Request body for renaming a course."""

    new_code: str | None = Field(None, min_length=1, max_length=20)
    name: str | None = Field(None, max_length=255)


class CourseArchiveResponse(BaseModel):
    """Result of archiving a course."""

    code: str
    archived: bool


class CourseDeleteResponse(BaseModel):
    """Result of deleting a course."""

    code: str
    deleted: bool
    counts: dict[str, int]


class CourseMergeRequest(BaseModel):
    """Request body for merging a course into another."""

    into: str = Field(..., min_length=1, max_length=20)


class CourseMergeResponse(BaseModel):
    """Result of a course merge."""

    moved_summaries: int
    conflict_weeks: list[int]
    review_items_created: int


@router.get(
    "/courses",
    response_model=list[CourseListItem],
    summary="List all courses",
    description="Returns all courses with aggregate stats: weeks covered, total artifacts, last updated.",
)
async def list_courses(
    include_archived: bool = Query(False, description="Include archived courses"),
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> list[CourseListItem]:
    """List all courses with aggregate stats."""
    course_stats = await course_service.list_courses_with_stats(
        session, user_id=user.id, include_archived=include_archived
    )
    return [CourseListItem(**cs) for cs in course_stats]


@router.get(
    "/courses/{course_code}",
    response_model=CourseDetailResponse,
    summary="Get course detail",
    description="Returns course info with per-week breakdown including artifact counts, summary status, and asset counts.",
)
async def get_course_detail(
    course_code: str,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> CourseDetailResponse:
    """Get course detail with per-week breakdown."""
    course = await course_service.get_course_by_code(session, course_code, user_id=user.id)
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
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> WeekDetailResponse:
    """Get full detail for a specific course week."""
    course = await course_service.get_course_by_code(session, course_code, user_id=user.id)
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


@router.patch(
    "/courses/{course_code}",
    response_model=CourseResponse,
    summary="Rename a course",
    description="Updates the course code and/or name. Children keep FK integrity.",
)
async def rename_course(
    course_code: str,
    body: CourseUpdateRequest,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> CourseResponse:
    """Rename a course."""
    try:
        course = await course_service.rename_course(
            session, user.id, course_code, new_code=body.new_code, name=body.name
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    await session.commit()
    return CourseResponse.model_validate(course)


@router.post(
    "/courses/{course_code}/archive",
    response_model=CourseArchiveResponse,
    summary="Archive a course",
    description="Hides the course from default listings. Data is retained; "
    "use ?include_archived=1 on GET /courses to see archived courses.",
)
async def archive_course(
    course_code: str,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> CourseArchiveResponse:
    """Archive a course."""
    try:
        course = await course_service.archive_course(session, user.id, course_code)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    await session.commit()
    return CourseArchiveResponse(code=course.code, archived=course.archived_at is not None)


@router.delete(
    "/courses/{course_code}",
    response_model=CourseDeleteResponse,
    summary="Delete a course",
    description="Deletes the course and all its database children. Requires "
    "an X-Confirm header matching the course code (428 otherwise). Uploaded "
    "files remain in storage.",
)
async def delete_course(
    course_code: str,
    x_confirm: str | None = Header(None, alias="X-Confirm"),
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> CourseDeleteResponse:
    """Delete a course (requires type-to-confirm header)."""
    if x_confirm != course_code:
        raise HTTPException(
            status_code=428,
            detail=f"Confirmation required: set the X-Confirm header to '{course_code}'",
        )

    try:
        counts = await course_service.delete_course(session, user.id, course_code)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    await session.commit()
    logger.info("course_delete_confirmed", course_code=course_code, user_id=user.id)
    return CourseDeleteResponse(code=course_code, deleted=True, counts=counts)


@router.post(
    "/courses/{course_code}/merge",
    response_model=CourseMergeResponse,
    summary="Merge a course into another",
    description="Moves all content into the target course. Colliding week "
    "summaries create review items instead of overwriting. The source course "
    "is archived afterwards.",
)
async def merge_course(
    course_code: str,
    body: CourseMergeRequest,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> CourseMergeResponse:
    """Merge a course into another course."""
    try:
        result = await course_service.merge_courses(
            session, user.id, course_code, into_code=body.into
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    await session.commit()
    return CourseMergeResponse(**result)

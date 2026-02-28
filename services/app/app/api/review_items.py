"""Review Items API endpoints."""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import ResolveReviewRequest, ReviewItemResponse
from app.core.database import get_session
from app.models.artifact import LectureArtifact
from app.models.course import Course
from app.pipeline.orchestrator import resume_pipeline
from app.services import review_service

logger = structlog.get_logger()

router = APIRouter()


@router.get("/review-items", response_model=list[ReviewItemResponse])
async def list_review_items(
    status: str = "pending",
    session: AsyncSession = Depends(get_session),
) -> list[ReviewItemResponse]:
    """List review items, default to pending."""
    if status == "pending":
        items = await review_service.list_pending_reviews(session)
    else:
        # For other statuses, do a simple query
        from app.models.review_item import ReviewItem

        result = await session.execute(
            select(ReviewItem)
            .where(ReviewItem.status == status)
            .order_by(ReviewItem.created_at.desc())
        )
        items = list(result.scalars().all())
    return [ReviewItemResponse.model_validate(item) for item in items]


@router.get("/review-items/{review_id}", response_model=ReviewItemResponse)
async def get_review_item(
    review_id: str,
    session: AsyncSession = Depends(get_session),
) -> ReviewItemResponse:
    """Get a single review item."""
    item = await review_service.get_review_item(session, review_id)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    return ReviewItemResponse.model_validate(item)


@router.post(
    "/review-items/{review_id}/resolve",
    response_model=ReviewItemResponse,
)
async def resolve_review_item(
    review_id: str,
    body: ResolveReviewRequest,
    session: AsyncSession = Depends(get_session),
) -> ReviewItemResponse:
    """Resolve a review item and resume the pipeline.

    Applies the resolution to the referenced entity, marks the review
    as resolved, and restarts the pipeline from the appropriate stage.
    """
    item = await review_service.get_review_item(session, review_id)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    if item.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Review item is already {item.status}",
        )

    resolution = body.resolution

    # Apply resolution to the entity
    if item.entity_type == "lecture_artifact":
        result = await session.execute(
            select(LectureArtifact).where(LectureArtifact.id == item.entity_id)
        )
        artifact = result.scalar_one_or_none()
        if not artifact:
            raise HTTPException(status_code=404, detail="Referenced artifact not found")

        # Apply classification fields from resolution
        if "course_code" in resolution:
            course_result = await session.execute(
                select(Course).where(Course.code == resolution["course_code"])
            )
            course = course_result.scalar_one_or_none()
            if course:
                artifact.course_id = course.id

        if "week" in resolution:
            artifact.week = resolution["week"]
        if "title" in resolution:
            artifact.title = resolution["title"]

        artifact.status = "classified"

    # Mark review as resolved
    try:
        item = await review_service.resolve_review_item(
            session, review_id, resolution
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await session.commit()

    # Resume pipeline from classify stage (next stage after classification)
    if item.entity_type == "lecture_artifact":
        try:
            resume_pipeline(item.entity_id, from_stage="extract")
        except Exception as e:
            logger.error(
                "pipeline_resume_failed",
                review_id=review_id,
                error=str(e),
            )

    return ReviewItemResponse.model_validate(item)


@router.post(
    "/review-items/{review_id}/dismiss",
    response_model=ReviewItemResponse,
)
async def dismiss_review_item(
    review_id: str,
    session: AsyncSession = Depends(get_session),
) -> ReviewItemResponse:
    """Dismiss a review item without resolving it."""
    try:
        item = await review_service.dismiss_review_item(session, review_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await session.commit()
    return ReviewItemResponse.model_validate(item)

"""Review Items API endpoints."""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_or_default
from app.api.schemas import ResolveReviewRequest, ReviewItemResponse
from app.core.database import get_session
from app.models.artifact import LectureArtifact
from app.models.user import User
from app.pipeline.orchestrator import resume_pipeline
from app.services import artifact_service, review_service

logger = structlog.get_logger()

router = APIRouter()


@router.get(
    "/review-items",
    response_model=list[ReviewItemResponse],
    summary="List review items",
    description="Lists review items filtered by status (default: pending). Returns payload, suggested values, and resolution details.",
)
async def list_review_items(
    status: str = "pending",
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> list[ReviewItemResponse]:
    """List review items, default to pending."""
    if status == "pending":
        items = await review_service.list_pending_reviews(session, user_id=user.id)
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


@router.get(
    "/review-items/{review_id}",
    response_model=ReviewItemResponse,
    summary="Get a review item",
    description="Returns a single review item by ID.",
)
async def get_review_item(
    review_id: str,
    user: User = Depends(get_current_user_or_default),
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
    summary="Resolve a review item",
    description="Applies the resolution to the referenced entity, marks the review as resolved, and resumes the pipeline from the extract stage.",
)
async def resolve_review_item(
    review_id: str,
    body: ResolveReviewRequest,
    user: User = Depends(get_current_user_or_default),
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

        # Apply classification fields from resolution (shared move logic)
        await artifact_service.apply_classification(
            session,
            artifact,
            course_code=resolution.get("course_code"),
            week=resolution.get("week"),
            title=resolution.get("title"),
        )

        artifact.status = "classified"

    # Mark review as resolved
    try:
        item = await review_service.resolve_review_item(session, review_id, resolution)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    await session.commit()

    # Resume pipeline from classify stage (next stage after classification)
    if item.entity_type == "lecture_artifact":
        try:
            resume_pipeline(item.entity_id, from_stage="extract", user_id=user.id)
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
    summary="Dismiss a review item",
    description="Dismisses a review item without applying any changes to the referenced entity.",
)
async def dismiss_review_item(
    review_id: str,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> ReviewItemResponse:
    """Dismiss a review item without resolving it."""
    try:
        item = await review_service.dismiss_review_item(session, review_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    await session.commit()
    return ReviewItemResponse.model_validate(item)

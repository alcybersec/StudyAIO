"""Business logic for Review Item management."""

from datetime import datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils import generate_id
from app.models.review_item import ReviewItem

logger = structlog.get_logger()


async def create_review_item(
    session: AsyncSession,
    review_type: str,
    entity_type: str,
    entity_id: str,
    payload: dict,
    suggested_values: dict,
) -> ReviewItem:
    """Create a new ReviewItem for human review.

    Args:
        session: Database session.
        review_type: Type of review (e.g., "classification_course").
        entity_type: Type of entity (e.g., "lecture_artifact").
        entity_id: ID of the entity needing review.
        payload: Context for the reviewer.
        suggested_values: System's best guesses.

    Returns:
        The created ReviewItem.
    """
    review = ReviewItem(
        id=generate_id(),
        review_type=review_type,
        entity_type=entity_type,
        entity_id=entity_id,
        payload_json=payload,
        suggested_values=suggested_values,
        status="pending",
        created_at=datetime.utcnow(),
    )
    session.add(review)
    await session.flush()

    logger.info(
        "review_item_created",
        review_id=review.id,
        review_type=review_type,
        entity_type=entity_type,
        entity_id=entity_id,
    )

    return review


async def list_pending_reviews(session: AsyncSession) -> list[ReviewItem]:
    """Get all pending review items.

    Args:
        session: Database session.

    Returns:
        List of pending ReviewItem records.
    """
    result = await session.execute(
        select(ReviewItem)
        .where(ReviewItem.status == "pending")
        .order_by(ReviewItem.created_at.desc())
    )
    return list(result.scalars().all())


async def get_review_item(session: AsyncSession, review_id: str) -> ReviewItem | None:
    """Get a single review item by ID.

    Args:
        session: Database session.
        review_id: ReviewItem UUID.

    Returns:
        ReviewItem if found, None otherwise.
    """
    result = await session.execute(
        select(ReviewItem).where(ReviewItem.id == review_id)
    )
    return result.scalar_one_or_none()


async def resolve_review_item(
    session: AsyncSession,
    review_id: str,
    resolution: dict,
) -> ReviewItem:
    """Resolve a pending review item with a resolution.

    Args:
        session: Database session.
        review_id: ReviewItem UUID.
        resolution: Resolution data dict.

    Returns:
        Updated ReviewItem.

    Raises:
        ValueError: If review item not found or already resolved.
    """
    item = await get_review_item(session, review_id)
    if not item:
        raise ValueError(f"ReviewItem {review_id} not found")
    if item.status != "pending":
        raise ValueError(f"ReviewItem {review_id} is already {item.status}")

    item.status = "resolved"
    item.resolution_json = resolution
    item.resolved_at = datetime.utcnow()
    await session.flush()

    logger.info(
        "review_item_resolved",
        review_id=review_id,
        entity_type=item.entity_type,
        entity_id=item.entity_id,
    )
    return item


async def dismiss_review_item(
    session: AsyncSession, review_id: str
) -> ReviewItem:
    """Dismiss a pending review item.

    Args:
        session: Database session.
        review_id: ReviewItem UUID.

    Returns:
        Updated ReviewItem.

    Raises:
        ValueError: If review item not found or already resolved.
    """
    item = await get_review_item(session, review_id)
    if not item:
        raise ValueError(f"ReviewItem {review_id} not found")
    if item.status != "pending":
        raise ValueError(f"ReviewItem {review_id} is already {item.status}")

    item.status = "dismissed"
    item.resolved_at = datetime.utcnow()
    await session.flush()

    logger.info("review_item_dismissed", review_id=review_id)
    return item


async def count_pending_reviews(session: AsyncSession) -> int:
    """Count pending review items.

    Args:
        session: Database session.

    Returns:
        Number of pending reviews.
    """
    result = await session.execute(
        select(func.count(ReviewItem.id)).where(ReviewItem.status == "pending")
    )
    return result.scalar_one()

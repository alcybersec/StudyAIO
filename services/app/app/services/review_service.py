"""Business logic for Review Item management."""

from datetime import datetime

import structlog
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

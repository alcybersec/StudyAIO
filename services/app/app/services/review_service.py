"""Business logic for Review Item management."""

from datetime import UTC, datetime

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
    *,
    user_id: str,
) -> ReviewItem:
    """Create a new ReviewItem for human review.

    Args:
        session: Database session.
        review_type: Type of review (e.g., "classification_course").
        entity_type: Type of entity (e.g., "lecture_artifact").
        entity_id: ID of the entity needing review.
        payload: Context for the reviewer.
        suggested_values: System's best guesses.
        user_id: Owner user UUID (required, keyword-only); stored on the row so
            every read can filter on it directly.

    Returns:
        The created ReviewItem.
    """
    review = ReviewItem(
        id=generate_id(),
        user_id=user_id,
        review_type=review_type,
        entity_type=entity_type,
        entity_id=entity_id,
        payload_json=payload,
        suggested_values=suggested_values,
        status="pending",
        created_at=datetime.now(UTC),
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

    # Emit inbox notification to the owner (best-effort). lecture_artifact is
    # the only type this needs to cover, because it is the only type anything
    # creates.
    try:
        if entity_type == "lecture_artifact":
            from app.models.artifact import LectureArtifact
            from app.services import notification_service

            result = await session.execute(
                select(LectureArtifact).where(
                    LectureArtifact.id == entity_id, LectureArtifact.user_id == user_id
                )
            )
            artifact = result.scalar_one_or_none()
            if artifact:
                filename = artifact.original_filename or entity_id
                await notification_service.notify_inbox(
                    session,
                    artifact.user_id,
                    kind="review",
                    title=f"Review needed: {filename}",
                    body="A file needs your review before processing can continue.",
                    href="/review",
                )
    except Exception:
        logger.warning("review_inbox_notification_failed", review_id=review.id, exc_info=True)

    return review


async def list_pending_reviews(session: AsyncSession, *, user_id: str) -> list[ReviewItem]:
    """Get all pending review items, scoped by owner.

    Ownership is ``ReviewItem.user_id``, the same predicate the id-addressed
    paths use, so an item listed here is openable and an openable item is listed.

    Args:
        session: Database session.
        user_id: Owner user UUID (required); only this user's items.

    Returns:
        List of pending ReviewItem records, newest first.
    """
    query = (
        select(ReviewItem)
        .where(ReviewItem.status == "pending")
        .order_by(ReviewItem.created_at.desc())
    )
    query = query.where(ReviewItem.user_id == user_id)
    result = await session.execute(query)
    return list(result.scalars().all())


async def list_reviews_by_status(
    session: AsyncSession, status: str, *, user_id: str
) -> list[ReviewItem]:
    """List review items with a given status, scoped by owner.

    The non-pending counterpart to list_pending_reviews. It exists so the
    API layer does not have to hand-roll the scoping -- the version
    inlined in the endpoint had none and listed every user's resolved and
    dismissed items (#53).

    Args:
        session: Database session.
        status: Review status to filter on (e.g. "resolved", "dismissed").
        user_id: Owner user UUID (required); only this user's items.

    Returns:
        List of ReviewItem records, newest first.
    """
    query = (
        select(ReviewItem).where(ReviewItem.status == status).order_by(ReviewItem.created_at.desc())
    )
    query = query.where(ReviewItem.user_id == user_id)
    result = await session.execute(query)
    return list(result.scalars().all())


# Ownership of a review item is the row's own ``user_id`` (R-010); there is no
# longer a predicate resolving it through the artifact or summary it references.
# Legacy rows orphaned before the column existed may keep a NULL ``user_id`` on
# prod. ``user_id = <caller>`` never matches NULL, so those items are invisible
# to everyone rather than public -- deliberately fail-closed.


async def get_review_item(
    session: AsyncSession, review_id: str, *, user_id: str
) -> ReviewItem | None:
    """Get a single review item by ID, scoped by owner.

    Ownership is the row's own ``user_id``.

    Args:
        session: Database session.
        review_id: ReviewItem UUID.
        user_id: Owner user UUID (required); only return the item when it belongs to this user.

    Returns:
        ReviewItem if found, None otherwise.
    """
    query = select(ReviewItem).where(ReviewItem.id == review_id)
    query = query.where(ReviewItem.user_id == user_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def resolve_review_item(
    session: AsyncSession,
    review_id: str,
    resolution: dict,
    *,
    user_id: str,
) -> ReviewItem:
    """Resolve a pending review item with a resolution.

    Args:
        session: Database session.
        review_id: ReviewItem UUID.
        resolution: Resolution data dict.
        user_id: Owner user UUID (required); only resolve an item that belongs to
            this user; a foreign item is reported as not found. Endpoints
            MUST pass this -- resolving mutates state and resumes a pipeline.

    Returns:
        Updated ReviewItem.

    Raises:
        ValueError: If review item not found or already resolved.
    """
    item = await get_review_item(session, review_id, user_id=user_id)
    if not item:
        raise ValueError(f"ReviewItem {review_id} not found")
    if item.status != "pending":
        raise ValueError(f"ReviewItem {review_id} is already {item.status}")

    item.status = "resolved"
    item.resolution_json = resolution
    item.resolved_at = datetime.now(UTC)
    await session.flush()

    logger.info(
        "review_item_resolved",
        review_id=review_id,
        entity_type=item.entity_type,
        entity_id=item.entity_id,
    )
    return item


async def dismiss_review_item(session: AsyncSession, review_id: str, *, user_id: str) -> ReviewItem:
    """Dismiss a pending review item.

    Args:
        session: Database session.
        review_id: ReviewItem UUID.
        user_id: Owner user UUID (required); only dismiss an item that belongs to
            this user; a foreign item is reported as not found. Endpoints
            MUST pass this -- dismissing mutates state.

    Returns:
        Updated ReviewItem.

    Raises:
        ValueError: If review item not found or already resolved.
    """
    item = await get_review_item(session, review_id, user_id=user_id)
    if not item:
        raise ValueError(f"ReviewItem {review_id} not found")
    if item.status != "pending":
        raise ValueError(f"ReviewItem {review_id} is already {item.status}")

    item.status = "dismissed"
    item.resolved_at = datetime.now(UTC)
    await session.flush()

    logger.info("review_item_dismissed", review_id=review_id)
    return item


async def count_pending_reviews(session: AsyncSession, *, user_id: str) -> int:
    """Count pending review items, scoped by owner.

    Uses the same ``user_id`` predicate as list_pending_reviews. The two must
    agree: this count is what the inbox badge shows, and a badge that
    disagrees with the list it links to is its own bug report.

    Args:
        session: Database session.
        user_id: Owner user UUID (required); only count items whose referenced entity
            belongs to this user.

    Returns:
        Number of pending reviews.
    """
    query = select(func.count(ReviewItem.id)).where(ReviewItem.status == "pending")
    query = query.where(ReviewItem.user_id == user_id)
    result = await session.execute(query)
    return result.scalar_one()

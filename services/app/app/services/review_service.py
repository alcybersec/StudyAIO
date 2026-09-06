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

    # Emit inbox notification to the artifact owner (best-effort)
    try:
        if entity_type == "lecture_artifact":
            from app.models.artifact import LectureArtifact
            from app.services import notification_service

            result = await session.execute(
                select(LectureArtifact).where(LectureArtifact.id == entity_id)
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


async def list_pending_reviews(
    session: AsyncSession, user_id: str | None = None
) -> list[ReviewItem]:
    """Get all pending review items.

    Args:
        session: Database session.

    Returns:
        List of pending ReviewItem records.
    """
    query = (
        select(ReviewItem)
        .where(ReviewItem.status == "pending")
        .order_by(ReviewItem.created_at.desc())
    )
    if user_id:
        # Scope via artifact's user_id
        from app.models.artifact import LectureArtifact

        query = query.join(
            LectureArtifact,
            ReviewItem.entity_id == LectureArtifact.id,
        ).where(LectureArtifact.user_id == user_id)
    result = await session.execute(query)
    return list(result.scalars().all())


async def list_reviews_by_status(
    session: AsyncSession, status: str, user_id: str | None = None
) -> list[ReviewItem]:
    """List review items with a given status, optionally scoped by owner.

    The non-pending counterpart to list_pending_reviews. It exists so the
    API layer does not have to hand-roll the ownership join -- the version
    inlined in the endpoint had no scoping at all and listed every user's
    resolved and dismissed items (#53).

    Args:
        session: Database session.
        status: Review status to filter on (e.g. "resolved", "dismissed").
        user_id: If provided, only items whose referenced entity belongs to
            this user. Endpoints MUST pass it.

    Returns:
        List of ReviewItem records, newest first.
    """
    query = (
        select(ReviewItem).where(ReviewItem.status == status).order_by(ReviewItem.created_at.desc())
    )
    if user_id is not None:
        query = query.where(_owned_by(user_id))
    result = await session.execute(query)
    return list(result.scalars().all())


def _owned_by(user_id: str):
    """A predicate matching review items whose referenced entity is user_id's.

    ReviewItem is polymorphic (entity_type + entity_id, no FK) and has no
    user_id column, so ownership has to be resolved per entity type:

      * ``lecture_artifact`` -> LectureArtifact.user_id  (pipeline/classify.py)
      * ``summary``          -> Summary -> Course.user_id (course_service
                                merge_week_conflict)

    An entity type not listed here matches nothing, so a new one is invisible
    rather than public. That is deliberate: an authorization check should fail
    closed, and a 404 on your own item is a bug report, while the other way
    round is an incident.
    """
    from sqlalchemy import or_

    from app.models.artifact import LectureArtifact
    from app.models.course import Course
    from app.models.summary import Summary

    owns_artifact = (
        select(LectureArtifact.id)
        .where(
            LectureArtifact.id == ReviewItem.entity_id,
            LectureArtifact.user_id == user_id,
        )
        .exists()
    )
    owns_summary = (
        select(Summary.id)
        .join(Course, Summary.course_id == Course.id)
        .where(Summary.id == ReviewItem.entity_id, Course.user_id == user_id)
        .exists()
    )
    return or_(owns_artifact, owns_summary)


async def get_review_item(
    session: AsyncSession, review_id: str, user_id: str | None = None
) -> ReviewItem | None:
    """Get a single review item by ID, optionally scoped by owner.

    ReviewItem has no user_id column of its own; ownership runs through the
    entity it references. See _owned_by for the per-entity-type mapping.

    Args:
        session: Database session.
        review_id: ReviewItem UUID.
        user_id: If provided, only return the item when the entity it
            references belongs to this user. Endpoints exposing review items
            by id MUST pass this; omitting it returns the item regardless of
            owner and is only appropriate for trusted internal callers.

    Returns:
        ReviewItem if found, None otherwise.
    """
    query = select(ReviewItem).where(ReviewItem.id == review_id)
    if user_id is not None:
        query = query.where(_owned_by(user_id))
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def resolve_review_item(
    session: AsyncSession,
    review_id: str,
    resolution: dict,
    user_id: str | None = None,
) -> ReviewItem:
    """Resolve a pending review item with a resolution.

    Args:
        session: Database session.
        review_id: ReviewItem UUID.
        resolution: Resolution data dict.
        user_id: If provided, only resolve an item whose artifact belongs to
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


async def dismiss_review_item(
    session: AsyncSession, review_id: str, user_id: str | None = None
) -> ReviewItem:
    """Dismiss a pending review item.

    Args:
        session: Database session.
        review_id: ReviewItem UUID.
        user_id: If provided, only dismiss an item whose artifact belongs to
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


async def count_pending_reviews(session: AsyncSession, user_id: str | None = None) -> int:
    """Count pending review items.

    Args:
        session: Database session.

    Returns:
        Number of pending reviews.
    """
    query = select(func.count(ReviewItem.id)).where(ReviewItem.status == "pending")
    if user_id:
        from app.models.artifact import LectureArtifact

        query = query.join(
            LectureArtifact,
            ReviewItem.entity_id == LectureArtifact.id,
        ).where(LectureArtifact.user_id == user_id)
    result = await session.execute(query)
    return result.scalar_one()

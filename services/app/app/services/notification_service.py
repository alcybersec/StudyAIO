"""Central notification dispatcher — routes events to configured channels."""

from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.utils import generate_id
from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference

logger = structlog.get_logger()

# Closed set of event types
EVENT_TYPES = [
    "pipeline_complete",
    "review_created",
    "cards_due",
    "exam_reminder",
    "weekly_digest",
]

CHANNELS = ["email", "telegram", "push"]

# Closed set of inbox notification kinds
INBOX_KINDS = ["pipeline", "review", "achievement", "deadline"]


# ── In-app inbox notifications ─────────────────────────────────────


async def create_inbox_notification(
    session: AsyncSession,
    user_id: str,
    kind: str,
    title: str,
    body: str | None = None,
    href: str | None = None,
) -> Notification:
    """Create an in-app inbox notification.

    Args:
        session: Database session.
        user_id: Recipient user UUID.
        kind: One of INBOX_KINDS.
        title: Short display title.
        body: Optional longer description.
        href: Optional frontend navigation target.

    Returns:
        The created Notification.
    """
    notification = Notification(
        id=generate_id(),
        user_id=user_id,
        kind=kind,
        title=title,
        body=body,
        href=href,
    )
    session.add(notification)
    await session.flush()
    logger.info("inbox_notification_created", user_id=user_id, kind=kind)
    return notification


async def notify_inbox(
    session: AsyncSession,
    user_id: str,
    kind: str,
    title: str,
    body: str | None = None,
    href: str | None = None,
) -> Notification | None:
    """Best-effort inbox notification — failures are logged, never raised.

    Args:
        session: Database session.
        user_id: Recipient user UUID.
        kind: One of INBOX_KINDS.
        title: Short display title.
        body: Optional longer description.
        href: Optional frontend navigation target.

    Returns:
        The created Notification, or None on failure.
    """
    try:
        return await create_inbox_notification(session, user_id, kind, title, body=body, href=href)
    except Exception:
        logger.warning("notify_inbox_failed", user_id=user_id, kind=kind, exc_info=True)
        return None


async def list_inbox_notifications(
    session: AsyncSession,
    user_id: str,
    unread_only: bool = False,
    limit: int = 50,
) -> list[Notification]:
    """List inbox notifications for a user, newest first.

    Args:
        session: Database session.
        user_id: The user's ID.
        unread_only: If True, only return unread notifications.
        limit: Maximum number of notifications to return.

    Returns:
        List of Notification records ordered newest-first.
    """
    query = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    query = query.order_by(Notification.created_at.desc()).limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


async def mark_notifications_read(
    session: AsyncSession,
    user_id: str,
    ids: list[str],
) -> int:
    """Mark notifications as read (idempotent — only unread rows change).

    Args:
        session: Database session.
        user_id: The user's ID (rows must belong to this user).
        ids: Notification IDs to mark read.

    Returns:
        Number of notifications newly marked read.
    """
    if not ids:
        return 0
    result = await session.execute(
        update(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.id.in_(ids),
            Notification.read_at.is_(None),
        )
        .values(read_at=datetime.now(UTC))
    )
    await session.flush()
    updated = result.rowcount or 0
    logger.info("notifications_marked_read", user_id=user_id, updated=updated)
    return updated


async def count_unread_notifications(session: AsyncSession, user_id: str) -> int:
    """Count unread inbox notifications for a user.

    Args:
        session: Database session.
        user_id: The user's ID.

    Returns:
        Number of unread notifications.
    """
    result = await session.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == user_id,
            Notification.read_at.is_(None),
        )
    )
    return result.scalar_one()


async def get_preferences(session: AsyncSession, user_id: str) -> list[NotificationPreference]:
    """Get all notification preferences for a user.

    Args:
        session: Database session.
        user_id: The user's ID.

    Returns:
        List of NotificationPreference records.
    """
    result = await session.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    return list(result.scalars().all())


async def update_preferences(
    session: AsyncSession,
    user_id: str,
    preferences: list[dict],
) -> list[NotificationPreference]:
    """Update notification preferences for a user.

    Creates or updates preference records for each channel × event_type.

    Args:
        session: Database session.
        user_id: The user's ID.
        preferences: List of dicts with channel, event_type, enabled.

    Returns:
        Updated list of NotificationPreference records.
    """
    for pref_data in preferences:
        channel = pref_data.get("channel", "")
        event_type = pref_data.get("event_type", "")
        enabled = pref_data.get("enabled", False)

        if channel not in CHANNELS or event_type not in EVENT_TYPES:
            continue

        result = await session.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.channel == channel,
                NotificationPreference.event_type == event_type,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.enabled = enabled
        else:
            pref = NotificationPreference(
                id=generate_id(),
                user_id=user_id,
                channel=channel,
                event_type=event_type,
                enabled=enabled,
            )
            session.add(pref)

    await session.flush()
    return await get_preferences(session, user_id)


async def seed_default_preferences(
    session: AsyncSession, user_id: str
) -> list[NotificationPreference]:
    """Seed default notification preferences for a user (all disabled).

    Args:
        session: Database session.
        user_id: The user's ID.

    Returns:
        List of created preference records.
    """
    existing = await get_preferences(session, user_id)
    if existing:
        return existing

    defaults = []
    for channel in CHANNELS:
        for event_type in EVENT_TYPES:
            pref = NotificationPreference(
                id=generate_id(),
                user_id=user_id,
                channel=channel,
                event_type=event_type,
                enabled=False,
            )
            session.add(pref)
            defaults.append(pref)

    await session.flush()
    logger.info("notification_defaults_seeded", user_id=user_id, count=len(defaults))
    return defaults


async def notify(
    session: AsyncSession,
    user_id: str,
    event_type: str,
    **kwargs: object,
) -> dict[str, bool]:
    """Dispatch a notification to all enabled channels for a user.

    Best-effort: failures are logged but never raised.

    Args:
        session: Database session.
        user_id: The user's ID.
        event_type: One of EVENT_TYPES.
        **kwargs: Event-specific data passed to channel senders.

    Returns:
        Dict mapping channel name to success boolean.
    """
    if not settings.notifications_enabled:
        return {}

    if event_type not in EVENT_TYPES:
        logger.warning("unknown_event_type", event_type=event_type)
        return {}

    results: dict[str, bool] = {}

    # Load user preferences for this event
    pref_result = await session.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == user_id,
            NotificationPreference.event_type == event_type,
            NotificationPreference.enabled == True,  # noqa: E712
        )
    )
    enabled_prefs = list(pref_result.scalars().all())

    if not enabled_prefs:
        return results

    # Load user email for email channel
    user_email = None
    for pref in enabled_prefs:
        if pref.channel == "email" and user_email is None:
            try:
                from app.models.user import User

                user_result = await session.execute(select(User.email).where(User.id == user_id))
                user_email = user_result.scalar_one_or_none()
            except Exception:
                logger.warning("notify_load_user_failed", user_id=user_id, exc_info=True)

        if pref.channel == "email" and user_email:
            try:
                from app.services import email_service

                sender = getattr(email_service, f"send_{event_type}", None)
                if sender:
                    results["email"] = await sender(user_email, **kwargs)
                else:
                    logger.warning("no_email_sender", event_type=event_type)
                    results["email"] = False
            except Exception:
                logger.warning("notify_email_failed", event_type=event_type, exc_info=True)
                results["email"] = False

        elif pref.channel == "telegram":
            try:
                from app.models.telegram_link import TelegramLink
                from app.services import telegram_service

                link_result = await session.execute(
                    select(TelegramLink).where(
                        TelegramLink.user_id == user_id,
                        TelegramLink.verified == True,  # noqa: E712
                    )
                )
                link = link_result.scalar_one_or_none()

                if link and link.chat_id:
                    sender = getattr(telegram_service, f"send_{event_type}", None)
                    if sender:
                        results["telegram"] = await sender(link.chat_id, **kwargs)
                    else:
                        logger.warning("no_telegram_sender", event_type=event_type)
                        results["telegram"] = False
                else:
                    results["telegram"] = False
            except Exception:
                logger.warning("notify_telegram_failed", event_type=event_type, exc_info=True)
                results["telegram"] = False

        elif pref.channel == "push":
            try:
                from app.services import push_service

                title = f"StudyAIO: {event_type.replace('_', ' ').title()}"
                body = _build_push_body(event_type, kwargs)
                sent = await push_service.send_push_notification(
                    session, user_id, title=title, body=body
                )
                results["push"] = sent > 0
            except Exception:
                logger.warning("notify_push_failed", event_type=event_type, exc_info=True)
                results["push"] = False

    return results


def _build_push_body(event_type: str, kwargs: dict[str, object]) -> str:
    """Build a human-readable push notification body for an event type."""
    if event_type == "pipeline_complete":
        filename = kwargs.get("filename", "file")
        return f"{filename} has been processed and is ready to study."
    if event_type == "cards_due":
        due_count = kwargs.get("due_count", 0)
        return f"You have {due_count} flashcard{'s' if due_count != 1 else ''} due for review."
    if event_type == "exam_reminder":
        title = kwargs.get("exam_title", "Exam")
        date = kwargs.get("exam_date", "")
        return f"{title} is coming up on {date}. Keep studying!"
    if event_type == "weekly_digest":
        return "Your weekly study digest is ready."
    return f"New {event_type.replace('_', ' ')} notification."


async def notify_pipeline_complete(
    session: AsyncSession,
    user_id: str,
    filename: str,
    course_code: str,
    week: int,
    flashcard_count: int,
    quiz_count: int,
) -> dict[str, bool]:
    """Send pipeline completion notification (inbox + configured channels)."""
    await notify_inbox(
        session,
        user_id,
        kind="pipeline",
        title=f"{filename} processed",
        body=f"{flashcard_count} flashcards and {quiz_count} quiz questions generated "
        f"for {course_code} week {week}.",
        href=f"/courses/{course_code}/weeks/{week}",
    )
    return await notify(
        session,
        user_id,
        "pipeline_complete",
        filename=filename,
        course_code=course_code,
        week=week,
        flashcard_count=flashcard_count,
        quiz_count=quiz_count,
    )


async def notify_review_created(
    session: AsyncSession,
    user_id: str,
    filename: str,
    course_code: str,
    week: int,
    flashcard_count: int = 0,
    quiz_count: int = 0,
) -> dict[str, bool]:
    """Send review item created notification (reuses pipeline_complete template)."""
    return await notify(
        session,
        user_id,
        "pipeline_complete",
        filename=filename,
        course_code=course_code,
        week=week,
        flashcard_count=flashcard_count,
        quiz_count=quiz_count,
    )


async def notify_cards_due(session: AsyncSession, user_id: str, due_count: int) -> dict[str, bool]:
    """Send cards due reminder notification."""
    return await notify(session, user_id, "cards_due", due_count=due_count)


async def notify_exam_reminder(
    session: AsyncSession,
    user_id: str,
    exam_title: str,
    course_code: str,
    exam_date: str,
) -> dict[str, bool]:
    """Send exam reminder notification."""
    return await notify(
        session,
        user_id,
        "exam_reminder",
        exam_title=exam_title,
        course_code=course_code,
        exam_date=exam_date,
    )

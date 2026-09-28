"""Feedback service — submit, list and triage in-app feedback.

Sentry records what crashed and the beta funnel records that someone stopped
after their first upload. Neither records *why*. That has to come from the
person, and until now there was nowhere for them to say it.
"""

import html

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feedback import FEEDBACK_KINDS, FEEDBACK_STATUSES, Feedback
from app.models.telegram_link import TelegramLink
from app.models.user import User

logger = structlog.get_logger()

#: Long enough for a real report, short enough that the column is not a dumping
#: ground. The UI counts down against the same number.
MAX_MESSAGE_LENGTH = 4000

#: How much of the message goes into the Telegram ping. The point of the ping is
#: "someone said something, go and read it", not to deliver the whole report.
PING_EXCERPT = 240


async def submit_feedback(
    session: AsyncSession,
    user_id: str,
    *,
    kind: str,
    message: str,
    route: str | None = None,
    app_version: str | None = None,
    user_agent: str | None = None,
) -> Feedback:
    """Record one piece of feedback. The caller commits.

    Args:
        session: Database session.
        user_id: Who is reporting.
        kind: One of `FEEDBACK_KINDS`.
        message: What they wrote.
        route: The route they were on, for reproducing it.
        app_version: Commit SHA of their build, so a fixed bug can be told apart
            from one still live.
        user_agent: Their browser.

    Returns:
        The stored Feedback.

    Raises:
        ValueError: If the kind is unknown or the message is empty or too long.
    """
    if kind not in FEEDBACK_KINDS:
        raise ValueError(f"Unknown feedback kind: {kind}")

    message = message.strip()
    if not message:
        raise ValueError("Feedback message is empty")
    if len(message) > MAX_MESSAGE_LENGTH:
        raise ValueError(f"Feedback message exceeds {MAX_MESSAGE_LENGTH} characters")

    entry = Feedback(
        user_id=user_id,
        kind=kind,
        message=message,
        route=route,
        app_version=app_version,
        # Truncate rather than reject: a long user-agent is the browser's doing,
        # and losing the whole report over it would be absurd.
        user_agent=user_agent[:500] if user_agent else None,
    )
    session.add(entry)
    await session.flush()

    logger.info(
        "feedback_submitted",
        feedback_id=entry.id,
        user_id=user_id,
        kind=kind,
        route=route,
        # Deliberately not the message: it is the user's words, and the
        # structured log is not where they belong.
        length=len(message),
    )
    return entry


async def notify_admins(session: AsyncSession, entry: Feedback, reporter_email: str) -> int:
    """Ping linked admins on Telegram that feedback arrived. Best effort.

    Feedback nobody reads is worse than no feedback, because it looks like a
    channel. This is the cheapest thing that makes it arrive somewhere a person
    is already looking.

    Never raises: the feedback is already stored and acknowledged by the time
    this runs, and a Telegram outage must not turn a successful submission into
    an error.

    Args:
        session: Database session.
        entry: The stored feedback.
        reporter_email: Who sent it, for the ping.

    Returns:
        How many admins were reached.
    """
    from app.services import telegram_service

    try:
        links = (
            (
                await session.execute(
                    select(TelegramLink)
                    .join(User, User.id == TelegramLink.user_id)
                    .where(User.role == "admin", User.is_active.is_(True))
                )
            )
            .scalars()
            .all()
        )
        if not links:
            return 0

        excerpt = entry.message[:PING_EXCERPT]
        if len(entry.message) > PING_EXCERPT:
            excerpt += "…"

        text = (
            f"<b>Feedback: {html.escape(entry.kind)}</b>\n\n"
            f"{html.escape(excerpt)}\n\n"
            f"From: {html.escape(reporter_email)}\n"
            f"Page: {html.escape(entry.route or 'unknown')}"
        )

        sent = 0
        for link in links:
            if await telegram_service.send_telegram_message(link.chat_id, text):
                sent += 1
        return sent
    except Exception:
        logger.warning("feedback_notify_failed", feedback_id=entry.id, exc_info=True)
        return 0


async def list_feedback(
    session: AsyncSession,
    *,
    status: str | None = None,
    kind: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Feedback], int]:
    """List feedback newest-first, with the reporter loaded.

    Args:
        session: Database session.
        status: Optional status filter.
        kind: Optional kind filter.
        offset: Pagination offset.
        limit: Pagination limit.

    Returns:
        (rows, total).
    """
    from sqlalchemy.orm import joinedload

    query = select(Feedback).options(joinedload(Feedback.user))
    count_query = select(func.count(Feedback.id))

    if status:
        query = query.where(Feedback.status == status)
        count_query = count_query.where(Feedback.status == status)
    if kind:
        query = query.where(Feedback.kind == kind)
        count_query = count_query.where(Feedback.kind == kind)

    total = (await session.execute(count_query)).scalar_one()
    query = query.order_by(Feedback.created_at.desc()).offset(offset).limit(limit)
    rows = list((await session.execute(query)).unique().scalars().all())
    return rows, total


async def set_status(session: AsyncSession, feedback_id: str, status: str) -> Feedback | None:
    """Move one piece of feedback through triage. The caller commits.

    Args:
        session: Database session.
        feedback_id: Which one.
        status: One of `FEEDBACK_STATUSES`.

    Returns:
        The updated Feedback, or None if it does not exist.

    Raises:
        ValueError: If the status is unknown.
    """
    if status not in FEEDBACK_STATUSES:
        raise ValueError(f"Unknown feedback status: {status}")

    entry = await session.get(Feedback, feedback_id)
    if not entry:
        return None

    entry.status = status
    await session.flush()
    logger.info("feedback_status_changed", feedback_id=feedback_id, status=status)
    return entry


async def count_by_status(session: AsyncSession) -> dict[str, int]:
    """Counts per status, so the admin nav can show an unread badge.

    Returns:
        Dict keyed by status; statuses with no rows are present as 0.
    """
    rows = (
        await session.execute(
            select(Feedback.status, func.count(Feedback.id)).group_by(Feedback.status)
        )
    ).all()
    counts = dict.fromkeys(FEEDBACK_STATUSES, 0)
    counts.update({status: count for status, count in rows})
    return counts

"""Telegram bot service for account linking and message sending."""

import secrets

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import TelegramLinkError
from app.core.utils import generate_id
from app.models.telegram_link import TelegramLink

logger = structlog.get_logger()


def _telegram_configured() -> bool:
    """Check if Telegram bot token is configured."""
    return bool(settings.telegram_bot_token.get_secret_value())


async def generate_link_token(session: AsyncSession, user_id: str) -> str:
    """Generate a deep-link token for Telegram account linking.

    Creates or updates a TelegramLink record with a fresh token.

    Args:
        session: Database session.
        user_id: The user's ID.

    Returns:
        The generated link token.
    """
    result = await session.execute(select(TelegramLink).where(TelegramLink.user_id == user_id))
    link = result.scalar_one_or_none()

    token = secrets.token_urlsafe(32)

    if link:
        link.link_token = token
        link.verified = False
        link.chat_id = None
        link.username = None
    else:
        link = TelegramLink(
            id=generate_id(),
            user_id=user_id,
            link_token=token,
        )
        session.add(link)

    await session.flush()
    logger.info("telegram_link_token_generated", user_id=user_id)
    return token


async def verify_link(
    session: AsyncSession, token: str, chat_id: int, username: str | None = None
) -> bool:
    """Verify a Telegram link using a deep-link token from /start command.

    Args:
        session: Database session.
        token: The link token from the deep-link URL.
        chat_id: The Telegram chat ID.
        username: The Telegram username (optional).

    Returns:
        True if link was verified successfully.

    Raises:
        TelegramLinkError: If token is invalid or expired.
    """
    result = await session.execute(select(TelegramLink).where(TelegramLink.link_token == token))
    link = result.scalar_one_or_none()

    if not link:
        raise TelegramLinkError("Invalid or expired link token")

    link.chat_id = chat_id
    link.username = username
    link.verified = True
    link.link_token = None  # Consume token

    await session.flush()
    logger.info("telegram_link_verified", user_id=link.user_id, chat_id=chat_id)
    return True


async def unlink(session: AsyncSession, user_id: str) -> bool:
    """Remove Telegram link for a user.

    Args:
        session: Database session.
        user_id: The user's ID.

    Returns:
        True if link was removed, False if none existed.
    """
    result = await session.execute(select(TelegramLink).where(TelegramLink.user_id == user_id))
    link = result.scalar_one_or_none()

    if not link:
        return False

    await session.delete(link)
    await session.flush()
    logger.info("telegram_unlinked", user_id=user_id)
    return True


async def get_link(session: AsyncSession, user_id: str) -> TelegramLink | None:
    """Get the Telegram link for a user.

    Args:
        session: Database session.
        user_id: The user's ID.

    Returns:
        TelegramLink or None.
    """
    result = await session.execute(select(TelegramLink).where(TelegramLink.user_id == user_id))
    return result.scalar_one_or_none()


async def send_telegram_message(chat_id: int, text: str) -> bool:
    """Send a message to a Telegram chat. Best-effort.

    Args:
        chat_id: Telegram chat ID.
        text: Message text (supports HTML formatting).

    Returns:
        True if sent successfully, False otherwise.
    """
    if not _telegram_configured():
        logger.debug("telegram_skipped_no_token", chat_id=chat_id)
        return False

    try:
        from aiogram import Bot

        bot = Bot(token=settings.telegram_bot_token.get_secret_value())
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
        await bot.session.close()

        logger.info("telegram_message_sent", chat_id=chat_id)
        return True

    except Exception:
        logger.warning("telegram_send_failed", chat_id=chat_id, exc_info=True)
        return False


async def handle_telegram_webhook(session: AsyncSession, update: dict) -> str:
    """Handle an incoming Telegram webhook update.

    Processes /start <token> commands for account linking.

    Args:
        session: Database session.
        update: The Telegram Update object as a dict.

    Returns:
        Response message to send back.
    """
    message = update.get("message", {})
    text = message.get("text", "")
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    from_user = message.get("from", {})
    username = from_user.get("username")

    if not chat_id:
        return "No chat ID found"

    if text.startswith("/start "):
        token = text[7:].strip()
        if not token:
            return "Welcome to StudyAIO Bot! Use the link from your Settings page to connect your account."

        try:
            await verify_link(session, token, chat_id, username)
            await session.commit()
            return "Your Telegram account has been linked to StudyAIO! You'll now receive notifications here."
        except TelegramLinkError:
            return (
                "Invalid or expired link token. Please generate a new link from your Settings page."
            )

    elif text.startswith("/start"):
        return (
            "Welcome to StudyAIO Bot! Use the link from your Settings page to connect your account."
        )

    return "Send /start with your link token to connect your StudyAIO account."


async def send_pipeline_complete(
    chat_id: int,
    filename: str,
    course_code: str,
    week: int,
    flashcard_count: int,
    quiz_count: int,
) -> bool:
    """Send pipeline completion notification via Telegram."""
    text = (
        f"<b>Processing Complete</b>\n\n"
        f"File: <b>{filename}</b>\n"
        f"Course: {course_code} (Week {week})\n\n"
        f"Generated:\n"
        f"- {flashcard_count} flashcards\n"
        f"- {quiz_count} quiz questions\n\n"
        f"Your study materials are ready!"
    )
    return await send_telegram_message(chat_id, text)


async def send_exam_reminder(
    chat_id: int, exam_title: str, course_code: str, exam_date: str
) -> bool:
    """Send exam reminder notification via Telegram."""
    text = (
        f"<b>Exam Reminder</b>\n\n"
        f"<b>{exam_title}</b>\n"
        f"Course: {course_code}\n"
        f"Date: {exam_date}\n\n"
        f"Don't forget to review your study materials!"
    )
    return await send_telegram_message(chat_id, text)


async def send_cards_due(chat_id: int, due_count: int) -> bool:
    """Send due flashcards reminder via Telegram."""
    text = (
        f"<b>Flashcards Due</b>\n\n"
        f"You have <b>{due_count}</b> flashcards due for review today.\n"
        f"Keep your streak alive!"
    )
    return await send_telegram_message(chat_id, text)


async def send_weekly_digest(
    chat_id: int,
    cards_reviewed: int,
    quiz_attempts: int,
    study_sessions: int,
    streak_days: int,
    due_count: int,
) -> bool:
    """Send weekly study digest via Telegram."""
    text = (
        f"<b>Weekly Study Digest</b>\n\n"
        f"Cards reviewed: <b>{cards_reviewed}</b>\n"
        f"Quiz attempts: <b>{quiz_attempts}</b>\n"
        f"Study sessions: <b>{study_sessions}</b>\n"
        f"Current streak: <b>{streak_days}</b> days\n\n"
    )
    if due_count > 0:
        text += f"You have <b>{due_count}</b> flashcards due. Keep it up!"
    else:
        text += "You're all caught up! Great job!"
    return await send_telegram_message(chat_id, text)

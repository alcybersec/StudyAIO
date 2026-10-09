"""Celery Beat scheduled notification tasks."""

from datetime import UTC, date, datetime, time, timedelta

import structlog
from sqlalchemy import func, select

from app.core.clock import user_now, user_today, utc_now, utc_today
from app.core.database import async_session_factory, run_async
from app.core.localday import local_day_end_utc
from app.core.redis import get_redis
from app.worker import celery_app

logger = structlog.get_logger()

# How many days ahead the deadline scan looks
DEADLINE_REMINDER_WINDOW_DAYS = 7

# Reminders and the digest go out at this hour in the user's own zone
# (ADR 0006, R-023). Beat fires hourly; each run picks the users it is 08:xx for.
REMINDER_LOCAL_HOUR = 8
SUNDAY = 6  # datetime.weekday()
# Send-claim keys outlive any local day (UTC-12..UTC+14) so a re-run can't resend.
_CLAIM_TTL_SECONDS = 48 * 3600


def _is_send_time(tz: str | None, *, sunday_only: bool = False) -> bool:
    """True when it is currently 08:xx (and Sunday, if asked) in the user's zone."""
    now = user_now(tz)
    if now.hour != REMINDER_LOCAL_HOUR:
        return False
    return not sunday_only or now.weekday() == SUNDAY


def _local_day_start_utc(tz: str | None) -> datetime:
    """UTC instant at which the user's current local day began."""
    now = user_now(tz)
    return datetime.combine(now.date(), time.min, tzinfo=now.tzinfo).astimezone(UTC)


def _claim_key(kind: str, user_id: str, local_date: date) -> str:
    return f"notif-sent:{kind}:{user_id}:{local_date.isoformat()}"


async def _claim_send(kind: str, user_id: str, local_date: date) -> bool:
    """Atomically claim the (user, kind, local date) send slot.

    Returns:
        True if this caller owns the slot, False if it was already claimed.
    """
    redis = await get_redis()
    return bool(
        await redis.set(_claim_key(kind, user_id, local_date), "1", nx=True, ex=_CLAIM_TTL_SECONDS)
    )


async def _release_send(kind: str, user_id: str, local_date: date) -> None:
    """Give the slot back after a failed send so the next hourly run can retry."""
    redis = await get_redis()
    await redis.delete(_claim_key(kind, user_id, local_date))


async def _send_deadline_reminders() -> int:
    """Emit inbox notifications for deadlines due within the reminder window.

    Idempotent: at most one notification per deadline per day (deduped on
    user, kind, href, and creation date).

    Returns:
        Number of notifications emitted.
    """
    from app.models.course import Course
    from app.models.deadline import Deadline
    from app.models.notification import Notification
    from app.models.user_settings import UserSettings
    from app.services import notification_service

    notified = 0
    # Fetch generously around the UTC date; each row is re-checked against its
    # owner's local day below.
    utc_day = utc_today()

    async with async_session_factory() as session:
        rows = await session.execute(
            select(
                Deadline.id.label("deadline_id"),
                Deadline.title,
                Deadline.due_date,
                Course.code.label("course_code"),
                Course.user_id,
                UserSettings.timezone,
            )
            .join(Course, Deadline.course_id == Course.id)
            .outerjoin(UserSettings, UserSettings.user_id == Course.user_id)
            .where(
                Deadline.due_date >= utc_day - timedelta(days=1),
                Deadline.due_date <= utc_day + timedelta(days=DEADLINE_REMINDER_WINDOW_DAYS + 1),
            )
        )

        for row in rows.all():
            tz = row.timezone
            if not _is_send_time(tz):
                continue
            today = user_today(tz)
            if not (today <= row.due_date <= today + timedelta(days=DEADLINE_REMINDER_WINDOW_DAYS)):
                continue
            start_of_today = _local_day_start_utc(tz)
            try:
                href = f"/courses/{row.course_code}/ops?deadline={row.deadline_id}"

                # ≤1 notification per deadline per day
                existing = await session.execute(
                    select(Notification.id).where(
                        Notification.user_id == row.user_id,
                        Notification.kind == "deadline",
                        Notification.href == href,
                        Notification.created_at >= start_of_today,
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                days_left = (row.due_date - today).days
                when = (
                    "today"
                    if days_left == 0
                    else f"in {days_left} day{'s' if days_left != 1 else ''}"
                )
                notification = await notification_service.notify_inbox(
                    session,
                    row.user_id,
                    kind="deadline",
                    title=f"{row.title} due {when}",
                    body=f"{row.course_code}: {row.title} is due on {row.due_date.isoformat()}.",
                    href=href,
                )
                if notification:
                    notified += 1
            except Exception:
                logger.warning(
                    "deadline_reminder_failed",
                    deadline_id=str(row.deadline_id),
                    exc_info=True,
                )

        await session.commit()

    return notified


async def _send_daily_reminders() -> int:
    """Send daily flashcard due reminders to opted-in users.

    Returns:
        Number of users notified.
    """
    from app.models.course import Course
    from app.models.flashcard import Flashcard
    from app.models.flashcard_review import FlashcardReview
    from app.models.notification_preference import NotificationPreference
    from app.models.user_settings import UserSettings
    from app.services import notification_service

    notified = 0

    async with async_session_factory() as session:
        # Find users with cards_due notifications enabled, with their zone
        pref_result = await session.execute(
            select(NotificationPreference.user_id, UserSettings.timezone)
            .outerjoin(UserSettings, UserSettings.user_id == NotificationPreference.user_id)
            .where(
                NotificationPreference.event_type == "cards_due",
                NotificationPreference.enabled == True,  # noqa: E712
            )
            .distinct()
        )
        recipients = [(row[0], row[1]) for row in pref_result.all() if _is_send_time(row[1])]

        if not recipients:
            return 0

        for user_id, tz in recipients:
            local_date = user_today(tz)
            if not await _claim_send("cards_due", user_id, local_date):
                continue
            try:
                cutoff = local_day_end_utc(tz)
                # Count cards due for this user
                due_result = await session.execute(
                    select(func.count(Flashcard.id))
                    .join(Course, Course.id == Flashcard.course_id)
                    .outerjoin(
                        FlashcardReview,
                        (Flashcard.id == FlashcardReview.flashcard_id)
                        & (FlashcardReview.user_id == user_id),
                    )
                    .where(
                        Course.user_id == user_id,
                        Flashcard.archived_at.is_(None),
                        (FlashcardReview.next_review_at < cutoff) | (FlashcardReview.id == None),  # noqa: E711
                    )
                )
                due_count = due_result.scalar() or 0

                if due_count > 0:
                    await notification_service.notify_cards_due(session, user_id, due_count)
                    notified += 1

            except Exception:
                await _release_send("cards_due", user_id, local_date)
                logger.warning(
                    "daily_reminder_user_failed",
                    user_id=user_id,
                    exc_info=True,
                )

        await session.commit()

    return notified


async def _send_weekly_digest() -> int:
    """Send weekly study digest to opted-in users.

    Returns:
        Number of users notified.
    """
    from app.models.course import Course
    from app.models.flashcard_review import FlashcardReview
    from app.models.notification_preference import NotificationPreference
    from app.models.quiz import QuizQuestion
    from app.models.quiz_attempt import QuizAttempt
    from app.models.study_session import StudySession
    from app.models.user_settings import UserSettings
    from app.services import notification_service

    notified = 0
    week_ago = utc_now() - timedelta(days=7)

    async with async_session_factory() as session:
        # Find users with weekly_digest enabled
        pref_result = await session.execute(
            select(NotificationPreference.user_id, UserSettings.timezone)
            .outerjoin(UserSettings, UserSettings.user_id == NotificationPreference.user_id)
            .where(
                NotificationPreference.event_type == "weekly_digest",
                NotificationPreference.enabled == True,  # noqa: E712
            )
            .distinct()
        )
        recipients = [
            (row[0], row[1]) for row in pref_result.all() if _is_send_time(row[1], sunday_only=True)
        ]

        if not recipients:
            return 0

        for user_id, tz in recipients:
            local_date = user_today(tz)
            if not await _claim_send("weekly_digest", user_id, local_date):
                continue
            try:
                # Cards reviewed this week
                cards_result = await session.execute(
                    select(func.count(FlashcardReview.id)).where(
                        FlashcardReview.user_id == user_id,
                        FlashcardReview.last_reviewed_at >= week_ago,
                    )
                )
                cards_reviewed = cards_result.scalar() or 0

                # Quiz attempts this week
                quiz_result = await session.execute(
                    select(func.count(QuizAttempt.id))
                    .join(QuizQuestion, QuizQuestion.id == QuizAttempt.quiz_question_id)
                    .join(Course, Course.id == QuizQuestion.course_id)
                    .where(
                        Course.user_id == user_id,
                        QuizAttempt.created_at >= week_ago,
                    )
                )
                quiz_attempts = quiz_result.scalar() or 0

                # Study sessions this week
                session_result = await session.execute(
                    select(func.count(StudySession.id)).where(
                        StudySession.user_id == user_id,
                        StudySession.session_date >= local_date - timedelta(days=7),
                    )
                )
                study_sessions = session_result.scalar() or 0

                await notification_service.notify(
                    session,
                    user_id,
                    "weekly_digest",
                    cards_reviewed=cards_reviewed,
                    quiz_attempts=quiz_attempts,
                    study_sessions=study_sessions,
                    streak_days=0,  # Simplified — streak calc is complex
                    due_count=0,
                )
                notified += 1

            except Exception:
                await _release_send("weekly_digest", user_id, local_date)
                logger.warning(
                    "weekly_digest_user_failed",
                    user_id=user_id,
                    exc_info=True,
                )

        await session.commit()

    return notified


@celery_app.task(name="app.pipeline.notification_tasks.send_deadline_reminders")
def send_deadline_reminders() -> dict:
    """Celery task: emit inbox notifications for approaching deadlines."""
    logger.info("deadline_reminders_started")
    try:
        notified = run_async(_send_deadline_reminders())
        logger.info("deadline_reminders_completed", notified=notified)
        return {"status": "completed", "notified": notified}
    except Exception:
        logger.error("deadline_reminders_failed", exc_info=True)
        return {"status": "failed", "notified": 0}


@celery_app.task(name="app.pipeline.notification_tasks.send_daily_reminders")
def send_daily_reminders() -> dict:
    """Celery task: send daily flashcard due reminders."""
    logger.info("daily_reminders_started")
    try:
        notified = run_async(_send_daily_reminders())
        logger.info("daily_reminders_completed", notified=notified)
        return {"status": "completed", "notified": notified}
    except Exception:
        logger.error("daily_reminders_failed", exc_info=True)
        return {"status": "failed", "notified": 0}


@celery_app.task(name="app.pipeline.notification_tasks.send_weekly_digest")
def send_weekly_digest() -> dict:
    """Celery task: send weekly study digest."""
    logger.info("weekly_digest_started")
    try:
        notified = run_async(_send_weekly_digest())
        logger.info("weekly_digest_completed", notified=notified)
        return {"status": "completed", "notified": notified}
    except Exception:
        logger.error("weekly_digest_failed", exc_info=True)
        return {"status": "failed", "notified": 0}

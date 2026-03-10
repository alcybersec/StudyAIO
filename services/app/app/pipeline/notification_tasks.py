"""Celery Beat scheduled notification tasks."""

from datetime import date, datetime, timedelta

import structlog
from sqlalchemy import func, select

from app.core.database import async_session_factory, run_async
from app.worker import celery_app

logger = structlog.get_logger()


async def _send_daily_reminders() -> int:
    """Send daily flashcard due reminders to opted-in users.

    Returns:
        Number of users notified.
    """
    from app.models.flashcard import Flashcard
    from app.models.flashcard_review import FlashcardReview
    from app.models.notification_preference import NotificationPreference
    from app.services import notification_service

    notified = 0

    async with async_session_factory() as session:
        # Find users with cards_due notifications enabled
        pref_result = await session.execute(
            select(NotificationPreference.user_id)
            .where(
                NotificationPreference.event_type == "cards_due",
                NotificationPreference.enabled == True,  # noqa: E712
            )
            .distinct()
        )
        user_ids = [row[0] for row in pref_result.all()]

        if not user_ids:
            return 0

        today = datetime.utcnow()

        for user_id in user_ids:
            try:
                # Count cards due for this user
                due_result = await session.execute(
                    select(func.count(Flashcard.id))
                    .outerjoin(FlashcardReview, Flashcard.id == FlashcardReview.flashcard_id)
                    .where(
                        Flashcard.user_id == user_id,
                        (FlashcardReview.next_review_at <= today) | (FlashcardReview.id == None),  # noqa: E711
                    )
                )
                due_count = due_result.scalar() or 0

                if due_count > 0:
                    await notification_service.notify_cards_due(session, user_id, due_count)
                    notified += 1

            except Exception:
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
    from app.models.flashcard_review import FlashcardReview
    from app.models.notification_preference import NotificationPreference
    from app.models.quiz_attempt import QuizAttempt
    from app.models.study_session import StudySession
    from app.services import notification_service

    notified = 0
    week_ago = datetime.utcnow() - timedelta(days=7)

    async with async_session_factory() as session:
        # Find users with weekly_digest enabled
        pref_result = await session.execute(
            select(NotificationPreference.user_id)
            .where(
                NotificationPreference.event_type == "weekly_digest",
                NotificationPreference.enabled == True,  # noqa: E712
            )
            .distinct()
        )
        user_ids = [row[0] for row in pref_result.all()]

        if not user_ids:
            return 0

        for user_id in user_ids:
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
                    select(func.count(QuizAttempt.id)).where(
                        QuizAttempt.user_id == user_id,
                        QuizAttempt.created_at >= week_ago,
                    )
                )
                quiz_attempts = quiz_result.scalar() or 0

                # Study sessions this week
                session_result = await session.execute(
                    select(func.count(StudySession.id)).where(
                        StudySession.user_id == user_id,
                        StudySession.session_date >= date.today() - timedelta(days=7),
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
                logger.warning(
                    "weekly_digest_user_failed",
                    user_id=user_id,
                    exc_info=True,
                )

        await session.commit()

    return notified


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

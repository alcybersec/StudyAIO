"""Celery task for periodic Google Calendar sync."""

import structlog
from sqlalchemy import select

from app.core.database import async_session_factory, run_async
from app.models.calendar_sync import CalendarSync
from app.worker import celery_app

logger = structlog.get_logger()


async def _sync_all() -> int:
    """Sync all connected calendars."""
    from app.services import gcal_service

    async with async_session_factory() as session:
        result = await session.execute(select(CalendarSync))
        syncs = list(result.scalars().all())

        synced = 0
        for cal_sync in syncs:
            try:
                await gcal_service.sync_calendar(session, cal_sync.user_id, cal_sync.id)
                synced += 1
            except Exception:
                logger.warning(
                    "calendar_periodic_sync_failed",
                    sync_id=cal_sync.id,
                    exc_info=True,
                )

        await session.commit()
        return synced


@celery_app.task(name="app.pipeline.calendar_task.sync_all_calendars")
def sync_all_calendars() -> dict:
    """Periodic task: sync all connected Google Calendars."""
    try:
        synced = run_async(_sync_all())
        logger.info("calendar_periodic_sync_complete", synced=synced)
        return {"synced": synced}
    except Exception:
        logger.warning("calendar_periodic_sync_error", exc_info=True)
        return {"synced": 0, "error": True}

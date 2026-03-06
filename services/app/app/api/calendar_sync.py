"""Google Calendar sync API endpoints."""

import structlog
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.calendar_schemas import (
    CalendarConnectRequest,
    CalendarConnectResponse,
    CalendarSyncInfo,
    CalendarSyncResult,
    CalendarSyncStatusResponse,
)
from app.api.deps import get_current_user_or_default
from app.core.database import get_session
from app.core.exceptions import CalendarSyncError
from app.core.rate_limit import limiter
from app.models.user import User
from app.services import gcal_service

logger = structlog.get_logger()

router = APIRouter(prefix="/calendar")


@router.post("/connect", response_model=CalendarConnectResponse)
@limiter.limit(lambda: "5/minute")
async def connect_calendar(
    request: Request,
    body: CalendarConnectRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user_or_default),
) -> CalendarConnectResponse:
    """Connect a Google Calendar using an OAuth authorization code."""
    cal_sync = await gcal_service.connect_google_calendar(
        session, user.id, body.auth_code
    )
    await session.commit()
    return CalendarConnectResponse(
        sync_id=cal_sync.id,
        calendar_id=cal_sync.google_calendar_id,
    )


@router.post("/sync", response_model=CalendarSyncResult)
@limiter.limit(lambda: "5/minute")
async def sync_calendars(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user_or_default),
) -> CalendarSyncResult:
    """Trigger manual sync for all connected calendars."""
    statuses = await gcal_service.get_sync_status(session, user.id)
    total_pushed = 0
    total_pulled = 0

    for status in statuses:
        try:
            result = await gcal_service.sync_calendar(session, user.id, status["id"])
            total_pushed += result["pushed"]
            total_pulled += result["pulled"]
        except CalendarSyncError:
            logger.warning("calendar_sync_failed", sync_id=status["id"], exc_info=True)

    await session.commit()
    return CalendarSyncResult(pushed=total_pushed, pulled=total_pulled)


@router.get("/status", response_model=CalendarSyncStatusResponse)
async def get_status(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user_or_default),
) -> CalendarSyncStatusResponse:
    """Return list of connected calendars with sync status."""
    statuses = await gcal_service.get_sync_status(session, user.id)
    return CalendarSyncStatusResponse(
        calendars=[CalendarSyncInfo(**s) for s in statuses]
    )


@router.delete("/disconnect/{sync_id}")
async def disconnect(
    sync_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user_or_default),
) -> dict:
    """Disconnect a Google Calendar integration."""
    deleted = await gcal_service.disconnect_calendar(session, user.id, sync_id)
    await session.commit()
    if not deleted:
        return {"detail": "Calendar sync not found"}
    return {"detail": "Calendar disconnected"}


@router.post("/webhook")
async def webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Handle Google Calendar push notifications (no auth — verified via channel token)."""
    channel_id = request.headers.get("x-goog-channel-id", "")
    resource_id = request.headers.get("x-goog-resource-id", "")

    if not channel_id:
        return Response(status_code=400)

    await gcal_service.handle_gcal_webhook(session, channel_id, resource_id)
    await session.commit()
    return Response(status_code=200)

"""API routes for the in-app notification inbox."""

from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_or_default
from app.core.database import get_session
from app.models.user import User
from app.services import notification_service

logger = structlog.get_logger()

router = APIRouter(prefix="/notifications")


class NotificationResponse(BaseModel):
    """A single inbox notification."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    title: str
    body: str | None = None
    href: str | None = None
    read_at: datetime | None = None
    created_at: datetime


class MarkReadRequest(BaseModel):
    """Request body for marking notifications read."""

    ids: list[str]


class MarkReadResponse(BaseModel):
    """Result of a mark-read operation."""

    updated: int


class UnreadCountResponse(BaseModel):
    """Unread notification count."""

    count: int


@router.get(
    "",
    response_model=list[NotificationResponse],
    summary="List inbox notifications",
    description="Returns the user's inbox notifications, newest first. "
    "Use ?unread=true to only return unread notifications.",
)
async def list_notifications(
    unread: bool = Query(False, description="Only return unread notifications"),
    limit: int = Query(50, ge=1, le=200, description="Max notifications to return"),
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> list[NotificationResponse]:
    """List inbox notifications for the current user."""
    notifications = await notification_service.list_inbox_notifications(
        session, user.id, unread_only=unread, limit=limit
    )
    return [NotificationResponse.model_validate(n) for n in notifications]


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    summary="Get unread notification count",
    description="Returns the number of unread inbox notifications.",
)
async def get_unread_count(
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> UnreadCountResponse:
    """Get the unread notification count for the current user."""
    count = await notification_service.count_unread_notifications(session, user.id)
    return UnreadCountResponse(count=count)


@router.post(
    "/mark-read",
    response_model=MarkReadResponse,
    summary="Mark notifications read",
    description="Marks the given notification IDs as read. Idempotent — "
    "already-read notifications are unaffected.",
)
async def mark_read(
    body: MarkReadRequest,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> MarkReadResponse:
    """Mark notifications as read."""
    updated = await notification_service.mark_notifications_read(session, user.id, body.ids)
    await session.commit()
    return MarkReadResponse(updated=updated)

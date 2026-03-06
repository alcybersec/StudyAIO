"""Pydantic schemas for Google Calendar sync endpoints."""

from pydantic import BaseModel


class CalendarConnectRequest(BaseModel):
    """Request body for connecting a Google Calendar."""

    auth_code: str


class CalendarConnectResponse(BaseModel):
    """Response after successfully connecting a calendar."""

    sync_id: str
    calendar_id: str


class CalendarSyncInfo(BaseModel):
    """Info about a connected calendar."""

    id: str
    google_calendar_id: str
    sync_direction: str
    last_synced_at: str | None
    event_count: int


class CalendarSyncStatusResponse(BaseModel):
    """Response with all connected calendars."""

    calendars: list[CalendarSyncInfo]


class CalendarDisconnectRequest(BaseModel):
    """Request body for disconnecting a calendar."""

    sync_id: str


class CalendarSyncResult(BaseModel):
    """Response after triggering a sync."""

    pushed: int
    pulled: int

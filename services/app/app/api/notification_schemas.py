"""Pydantic schemas for notification API endpoints."""

from pydantic import BaseModel


class NotificationPreferenceItem(BaseModel):
    """A single notification preference entry."""

    channel: str
    event_type: str
    enabled: bool


class NotificationPreferencesResponse(BaseModel):
    """Response containing all notification preferences for a user."""

    preferences: list[NotificationPreferenceItem]


class UpdatePreferencesRequest(BaseModel):
    """Request to update notification preferences."""

    preferences: list[NotificationPreferenceItem]


class TelegramLinkResponse(BaseModel):
    """Response after generating a Telegram deep-link token."""

    link_token: str
    bot_username: str
    deep_link: str


class TelegramStatusResponse(BaseModel):
    """Response showing current Telegram link status."""

    linked: bool
    username: str | None = None
    verified: bool = False


class PushSubscribeRequest(BaseModel):
    """Request to subscribe to Web Push notifications."""

    endpoint: str
    p256dh: str
    auth: str


class PushUnsubscribeRequest(BaseModel):
    """Request to unsubscribe from Web Push notifications."""

    endpoint: str


class VapidKeyResponse(BaseModel):
    """Response containing the VAPID public key."""

    public_key: str


class TestNotificationRequest(BaseModel):
    """Request to send a test notification."""

    channel: str


class TestNotificationResponse(BaseModel):
    """Response after sending a test notification."""

    success: bool
    channel: str
    message: str

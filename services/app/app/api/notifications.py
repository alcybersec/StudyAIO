"""Notification API endpoints for preferences and Telegram linking."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_or_default
from app.api.notification_schemas import (
    NotificationPreferenceItem,
    NotificationPreferencesResponse,
    PushSubscribeRequest,
    PushUnsubscribeRequest,
    TelegramLinkResponse,
    TelegramStatusResponse,
    TestNotificationRequest,
    TestNotificationResponse,
    UpdatePreferencesRequest,
    VapidKeyResponse,
)
from app.config import settings
from app.core.database import get_session
from app.core.rate_limit import limiter
from app.models.user import User
from app.services import notification_service, push_service, telegram_service

logger = structlog.get_logger()

router = APIRouter(prefix="/notifications")


@router.get("/preferences", response_model=NotificationPreferencesResponse)
async def get_preferences(
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> NotificationPreferencesResponse:
    """Get notification preferences for the current user.

    Seeds default preferences if none exist.
    """
    prefs = await notification_service.get_preferences(session, user.id)
    if not prefs:
        prefs = await notification_service.seed_default_preferences(session, user.id)
        await session.commit()

    items = [
        NotificationPreferenceItem(channel=p.channel, event_type=p.event_type, enabled=p.enabled)
        for p in prefs
    ]
    return NotificationPreferencesResponse(preferences=items)


@router.put("/preferences", response_model=NotificationPreferencesResponse)
async def update_preferences(
    body: UpdatePreferencesRequest,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> NotificationPreferencesResponse:
    """Update notification preferences for the current user."""
    prefs = await notification_service.update_preferences(
        session,
        user.id,
        [p.model_dump() for p in body.preferences],
    )
    await session.commit()

    items = [
        NotificationPreferenceItem(channel=p.channel, event_type=p.event_type, enabled=p.enabled)
        for p in prefs
    ]
    return NotificationPreferencesResponse(preferences=items)


@router.post("/telegram/link", response_model=TelegramLinkResponse)
@limiter.limit("5/minute")
async def generate_telegram_link(
    request: Request,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> TelegramLinkResponse:
    """Generate a Telegram deep-link token for account linking."""
    bot_token = settings.telegram_bot_token.get_secret_value()
    if not bot_token:
        raise HTTPException(status_code=400, detail="Telegram bot not configured")

    token = await telegram_service.generate_link_token(session, user.id)
    await session.commit()

    # Extract bot username from token (format: <id>:<secret>)
    # We need the bot username for the deep link — use a placeholder if not derivable
    bot_username = (
        settings.telegram_webhook_url.split("/")[-1]
        if settings.telegram_webhook_url
        else "StudyAIOBot"
    )

    deep_link = f"https://t.me/{bot_username}?start={token}"

    return TelegramLinkResponse(
        link_token=token,
        bot_username=bot_username,
        deep_link=deep_link,
    )


@router.delete("/telegram/unlink", response_model=TelegramStatusResponse)
async def unlink_telegram(
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> TelegramStatusResponse:
    """Unlink Telegram account from the current user."""
    await telegram_service.unlink(session, user.id)
    await session.commit()
    return TelegramStatusResponse(linked=False)


@router.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Handle incoming Telegram webhook updates.

    Verifies X-Telegram-Bot-Api-Secret-Token header for security.
    No user auth required (Telegram sends updates directly).
    """
    # Verify webhook secret
    expected_secret = settings.telegram_webhook_url
    received_secret = request.headers.get("x-telegram-bot-api-secret-token", "")

    # If a webhook URL is configured, use it as a simple shared secret check
    if expected_secret and received_secret != expected_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    body = await request.json()
    response_text = await telegram_service.handle_telegram_webhook(session, body)

    return {"ok": True, "response": response_text}


@router.get("/push/vapid-key", response_model=VapidKeyResponse)
async def get_vapid_key() -> VapidKeyResponse:
    """Get the VAPID public key for Web Push subscriptions."""
    if not settings.vapid_public_key:
        raise HTTPException(status_code=400, detail="Web Push not configured")
    return VapidKeyResponse(public_key=settings.vapid_public_key)


@router.post("/push/subscribe")
async def push_subscribe(
    body: PushSubscribeRequest,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Subscribe to Web Push notifications."""
    sub = await push_service.subscribe(
        session,
        user_id=user.id,
        endpoint=body.endpoint,
        p256dh=body.p256dh,
        auth=body.auth,
    )
    await session.commit()
    return {"id": sub.id, "detail": "Subscribed to push notifications"}


@router.delete("/push/unsubscribe")
async def push_unsubscribe(
    body: PushUnsubscribeRequest,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Unsubscribe from Web Push notifications."""
    deleted = await push_service.unsubscribe(session, user_id=user.id, endpoint=body.endpoint)
    await session.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return {"detail": "Unsubscribed from push notifications"}


@router.post("/test", response_model=TestNotificationResponse)
@limiter.limit("3/minute")
async def test_notification(
    request: Request,
    body: TestNotificationRequest,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> TestNotificationResponse:
    """Send a test notification via the specified channel."""
    if body.channel == "email":
        if not user.email:
            raise HTTPException(status_code=400, detail="No email address on account")

        from app.services import email_service

        success = await email_service.send_email(
            user.email,
            "StudyAIO: Test Notification",
            "<h2>Test Notification</h2><p>This is a test notification from StudyAIO. "
            "If you received this, email notifications are working correctly!</p>",
        )
        return TestNotificationResponse(
            success=success,
            channel="email",
            message="Test email sent" if success else "Failed to send test email",
        )

    elif body.channel == "telegram":
        link = await telegram_service.get_link(session, user.id)
        if not link or not link.verified or not link.chat_id:
            raise HTTPException(
                status_code=400,
                detail="Telegram not linked or not verified",
            )

        success = await telegram_service.send_telegram_message(
            link.chat_id,
            "<b>Test Notification</b>\n\nThis is a test notification from StudyAIO. "
            "If you received this, Telegram notifications are working correctly!",
        )
        return TestNotificationResponse(
            success=success,
            channel="telegram",
            message="Test message sent" if success else "Failed to send test message",
        )

    elif body.channel == "push":
        sent = await push_service.send_push_notification(
            session,
            user.id,
            title="StudyAIO: Test Notification",
            body="This is a test push notification from StudyAIO. "
            "If you see this, Web Push notifications are working!",
        )
        return TestNotificationResponse(
            success=sent > 0,
            channel="push",
            message=f"Test push sent to {sent} device(s)"
            if sent > 0
            else "No active push subscriptions",
        )

    else:
        raise HTTPException(status_code=400, detail=f"Unknown channel: {body.channel}")

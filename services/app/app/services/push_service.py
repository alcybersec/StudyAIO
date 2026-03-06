"""Web Push notification service — subscribe, unsubscribe, send."""

import json

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.utils import generate_id
from app.models.push_subscription import PushSubscription

logger = structlog.get_logger()


async def subscribe(
    session: AsyncSession,
    user_id: str,
    endpoint: str,
    p256dh: str,
    auth: str,
) -> PushSubscription:
    """Subscribe a user to Web Push notifications.

    Upserts — if endpoint already exists for user, updates keys.

    Args:
        session: Database session.
        user_id: The user's ID.
        endpoint: Push service endpoint URL.
        p256dh: Client public key.
        auth: Client auth secret.

    Returns:
        The created or updated PushSubscription.
    """
    result = await session.execute(
        select(PushSubscription).where(
            PushSubscription.user_id == user_id,
            PushSubscription.endpoint == endpoint,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.p256dh = p256dh
        existing.auth = auth
        await session.flush()
        logger.info("push_subscription_updated", user_id=user_id)
        return existing

    sub = PushSubscription(
        id=generate_id(),
        user_id=user_id,
        endpoint=endpoint,
        p256dh=p256dh,
        auth=auth,
    )
    session.add(sub)
    await session.flush()
    logger.info("push_subscription_created", user_id=user_id)
    return sub


async def unsubscribe(
    session: AsyncSession,
    user_id: str,
    endpoint: str,
) -> bool:
    """Remove a push subscription.

    Args:
        session: Database session.
        user_id: The user's ID.
        endpoint: Push service endpoint URL.

    Returns:
        True if a subscription was deleted.
    """
    result = await session.execute(
        delete(PushSubscription).where(
            PushSubscription.user_id == user_id,
            PushSubscription.endpoint == endpoint,
        )
    )
    deleted = result.rowcount > 0
    if deleted:
        logger.info("push_subscription_removed", user_id=user_id)
    return deleted


async def send_push_notification(
    session: AsyncSession,
    user_id: str,
    title: str,
    body: str,
    url: str | None = None,
) -> int:
    """Send a Web Push notification to all subscriptions for a user.

    Cleans up stale subscriptions (410/404) automatically.

    Args:
        session: Database session.
        user_id: The user's ID.
        title: Notification title.
        body: Notification body text.
        url: Optional URL to open on click.

    Returns:
        Number of successfully sent notifications.
    """
    private_key = settings.vapid_private_key.get_secret_value()
    if not private_key:
        logger.warning("push_not_configured", reason="vapid_private_key not set")
        return 0

    result = await session.execute(
        select(PushSubscription).where(PushSubscription.user_id == user_id)
    )
    subscriptions = list(result.scalars().all())

    if not subscriptions:
        return 0

    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        logger.warning("pywebpush_not_installed")
        return 0

    payload = json.dumps({
        "title": title,
        "body": body,
        "url": url or "/",
    })

    vapid_claims = {
        "sub": f"mailto:{settings.vapid_admin_email}",
    }

    sent = 0
    stale_ids: list[str] = []

    for sub in subscriptions:
        subscription_info = {
            "endpoint": sub.endpoint,
            "keys": {
                "p256dh": sub.p256dh,
                "auth": sub.auth,
            },
        }

        try:
            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=private_key,
                vapid_claims=vapid_claims,
            )
            sent += 1
        except WebPushException as e:
            status_code = getattr(e, "response", None)
            status = getattr(status_code, "status_code", None) if status_code else None
            if status in (404, 410):
                stale_ids.append(sub.id)
                logger.info("push_subscription_stale", sub_id=sub.id, status=status)
            else:
                logger.warning("push_send_failed", sub_id=sub.id, error=str(e))
        except Exception:
            logger.warning("push_send_error", sub_id=sub.id, exc_info=True)

    # Clean up stale subscriptions
    if stale_ids:
        await session.execute(
            delete(PushSubscription).where(PushSubscription.id.in_(stale_ids))
        )
        logger.info("push_stale_cleaned", count=len(stale_ids))

    return sent

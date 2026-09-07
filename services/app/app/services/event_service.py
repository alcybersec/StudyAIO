"""Pipeline event publishing for SSE support.

Events are fanned out on a **per-owner** Redis channel,
``pipeline:events:{user_id}``. There is deliberately no instance-wide channel:
a subscriber can only ever name one user's channel, so the SSE endpoint cannot
hand one tenant another tenant's events even if its own filtering is wrong
(#69 — it was wrong, and a single global channel is what made that a
cross-tenant leak rather than a display bug).

``user_id`` is therefore keyword-only and **required** on both publish
functions. A new call site that has no owner to hand over fails at the call,
not silently at runtime by broadcasting to everyone.
"""

import json

import structlog
from redis.asyncio import Redis

from app.config import settings

logger = structlog.get_logger()

PIPELINE_EVENTS_CHANNEL_PREFIX = "pipeline:events"


def pipeline_events_channel(user_id: str) -> str:
    """Redis pub/sub channel carrying one user's pipeline events.

    Args:
        user_id: Owner user UUID.

    Returns:
        The channel name for that owner.
    """
    return f"{PIPELINE_EVENTS_CHANNEL_PREFIX}:{user_id}"


async def publish_pipeline_event(
    artifact_id: str,
    stage: str,
    status: str,
    message: str | None = None,
    *,
    user_id: str | None,
) -> None:
    """Publish a pipeline event to the owner's Redis pub/sub channel.

    Args:
        artifact_id: Artifact UUID.
        stage: Pipeline stage name.
        status: Event status (started, completed, failed).
        message: Optional human-readable message. Must be safe to show the
            owner — never raw exception text (see the stage tasks).
        user_id: Owner user UUID. Required. ``None`` means the caller could not
            determine an owner, in which case the event is dropped rather than
            delivered to a guess: there is no channel that is correct for an
            unowned event, and the pipeline logs already carry the detail.
    """
    if not user_id:
        # Fail closed. An unowned event has no safe recipient.
        logger.warning(
            "event_publish_skipped_no_owner",
            artifact_id=artifact_id,
            stage=stage,
            status=status,
        )
        return

    event = {
        "artifact_id": artifact_id,
        "stage": stage,
        "status": status,
        "message": message,
        "user_id": user_id,
    }

    try:
        redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=settings.redis_socket_timeout,
            socket_timeout=settings.redis_socket_timeout,
        )
        await redis.publish(pipeline_events_channel(user_id), json.dumps(event))
        await redis.aclose()
    except Exception as e:
        # SSE is best-effort — don't break pipeline on publish failure
        logger.warning("event_publish_failed", error=str(e), event=event)


def publish_pipeline_event_sync(
    artifact_id: str,
    stage: str,
    status: str,
    message: str | None = None,
    *,
    user_id: str | None,
) -> None:
    """Sync wrapper for publishing pipeline events from Celery tasks.

    Args:
        artifact_id: Artifact UUID.
        stage: Pipeline stage name.
        status: Event status (started, completed, failed).
        message: Optional human-readable message.
        user_id: Owner user UUID. Required; see ``publish_pipeline_event``.
    """
    import asyncio

    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(
            publish_pipeline_event(artifact_id, stage, status, message, user_id=user_id)
        )
        loop.close()
    except Exception as e:
        logger.warning("event_publish_sync_failed", error=str(e))

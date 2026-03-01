"""Pipeline event publishing for SSE support."""

import json

import structlog
from redis.asyncio import Redis

from app.config import settings

logger = structlog.get_logger()

PIPELINE_EVENTS_CHANNEL = "pipeline:events"


async def publish_pipeline_event(
    artifact_id: str,
    stage: str,
    status: str,
    message: str | None = None,
) -> None:
    """Publish a pipeline event to Redis pub/sub.

    Args:
        artifact_id: Artifact UUID.
        stage: Pipeline stage name.
        status: Event status (started, completed, failed).
        message: Optional human-readable message.
    """
    event = {
        "artifact_id": artifact_id,
        "stage": stage,
        "status": status,
        "message": message,
    }

    try:
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        await redis.publish(PIPELINE_EVENTS_CHANNEL, json.dumps(event))
        await redis.aclose()
    except Exception as e:
        # SSE is best-effort — don't break pipeline on publish failure
        logger.warning("event_publish_failed", error=str(e), event=event)


def publish_pipeline_event_sync(
    artifact_id: str,
    stage: str,
    status: str,
    message: str | None = None,
) -> None:
    """Sync wrapper for publishing pipeline events from Celery tasks.

    Args:
        artifact_id: Artifact UUID.
        stage: Pipeline stage name.
        status: Event status (started, completed, failed).
        message: Optional human-readable message.
    """
    import asyncio

    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(publish_pipeline_event(artifact_id, stage, status, message))
        loop.close()
    except Exception as e:
        logger.warning("event_publish_sync_failed", error=str(e))

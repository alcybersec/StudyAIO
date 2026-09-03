"""Async Redis cache utilities for API responses."""

import json

import structlog
from redis.asyncio import Redis

from app.config import settings

logger = structlog.get_logger()

DASHBOARD_TTL_SECONDS = 30


def dashboard_cache_key(user_id: str) -> str:
    """Return the Redis key for a user's cached dashboard response."""
    return f"cache:dashboard:{user_id}"


async def check_redis_connectivity() -> bool:
    """Check Redis connectivity with a PING command.

    Returns True if Redis is reachable, False otherwise.
    """
    try:
        redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=settings.redis_socket_timeout,
            socket_timeout=settings.redis_socket_timeout,
        )
        try:
            return await redis.ping()
        finally:
            await redis.aclose()
    except Exception:
        return False


async def cache_get(key: str) -> dict | None:
    """Fetch a JSON value from Redis cache. Returns None on miss or error."""
    try:
        redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=settings.redis_socket_timeout,
            socket_timeout=settings.redis_socket_timeout,
        )
        try:
            raw = await redis.get(key)
            if raw is not None:
                return json.loads(raw)
        finally:
            await redis.aclose()
    except Exception:
        logger.debug("cache_get_failed", key=key, exc_info=True)
    return None


async def cache_set(key: str, value: dict, ttl: int = DASHBOARD_TTL_SECONDS) -> None:
    """Store a JSON value in Redis with a TTL. Best-effort, never raises."""
    try:
        redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=settings.redis_socket_timeout,
            socket_timeout=settings.redis_socket_timeout,
        )
        try:
            await redis.setex(key, ttl, json.dumps(value))
        finally:
            await redis.aclose()
    except Exception:
        logger.debug("cache_set_failed", key=key, exc_info=True)


async def cache_delete_pattern(pattern: str) -> None:
    """Delete all keys matching a pattern. Best-effort, never raises."""
    try:
        redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=settings.redis_socket_timeout,
            socket_timeout=settings.redis_socket_timeout,
        )
        try:
            cursor = 0
            while True:
                cursor, keys = await redis.scan(cursor=cursor, match=pattern, count=100)
                if keys:
                    await redis.delete(*keys)
                if cursor == 0:
                    break
        finally:
            await redis.aclose()
    except Exception:
        logger.debug("cache_delete_pattern_failed", pattern=pattern, exc_info=True)


async def cache_delete(key: str) -> None:
    """Delete a single cache key. Best-effort, never raises."""
    try:
        redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=settings.redis_socket_timeout,
            socket_timeout=settings.redis_socket_timeout,
        )
        try:
            await redis.delete(key)
        finally:
            await redis.aclose()
    except Exception:
        logger.debug("cache_delete_failed", key=key, exc_info=True)

"""Redis client setup."""

from redis.asyncio import Redis

from app.config import settings

redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


async def get_redis() -> Redis:
    """Dependency that provides a Redis client."""
    return redis_client

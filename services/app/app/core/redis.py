"""Redis client setup."""

from redis.asyncio import Redis

from app.config import settings

redis_client = Redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=settings.redis_socket_timeout,
    socket_timeout=settings.redis_socket_timeout,
)


async def get_redis() -> Redis:
    """Dependency that provides a Redis client."""
    return redis_client

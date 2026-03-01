"""Async SQLAlchemy database setup."""

import asyncio

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=5,
    max_overflow=10,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


async def get_session() -> AsyncSession:
    """Dependency that provides an async database session."""
    async with async_session_factory() as session:
        yield session


def run_async(coro):
    """Run an async coroutine from a sync Celery task.

    Disposes the engine connection pool first to avoid
    'attached to a different loop' errors when Celery reuses
    worker processes across tasks.
    """
    # Dispose stale connections synchronously — avoids trying to
    # close asyncpg connections on a dead event loop.
    engine.sync_engine.dispose()
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

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
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_recycle=settings.db_pool_recycle,
    pool_pre_ping=True,
    # asyncpg waits 60 seconds to connect by default. An unreachable database
    # then hangs every request for a full minute before failing, which reads as
    # a deadlock rather than an outage — and in the unit suite it was exactly
    # that: `tests/unit/api/test_uploads.py` took 60s *per test* because two
    # endpoints open their own session outside the overridable dependency
    # (GL#6). Bounded here so a bad DSN or a down database fails fast.
    connect_args={"timeout": settings.db_connect_timeout},
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


async def check_db_connectivity() -> bool:
    """Check database connectivity with a simple SELECT 1 query.

    Returns True if the database is reachable, False otherwise.
    """
    try:
        from sqlalchemy import text

        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def run_async(coro):
    """Run an async coroutine from a sync Celery task.

    Disposes the engine connection pool first to avoid
    'attached to a different loop' errors when Celery reuses
    worker processes across tasks.
    """
    # Drop the pool without closing its connections. They belong to an event
    # loop that is already gone, so closing them would await on asyncpg outside
    # a greenlet context — SQLAlchemy logs that as MissingGreenlet on every
    # task. close=False swaps in a fresh pool and abandons the old sockets.
    engine.sync_engine.dispose(close=False)
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

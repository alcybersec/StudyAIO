"""Integration test fixtures using testcontainers.

Provides real Postgres (pgvector) + Redis for integration testing.
Environment variables are set before any app code is imported.
"""

import os

import pytest
import pytest_asyncio
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

# ── Session-scoped containers ────────────────────────────────────────


@pytest.fixture(scope="session")
def postgres_container():
    """Start a Postgres container with pgvector for the test session."""
    # Skip container startup if DATABASE_URL is already set (e.g., CI with services)
    if os.environ.get("DATABASE_URL"):
        yield None
        return

    with PostgresContainer(
        image="pgvector/pgvector:pg16",
        username="testuser",
        password="testpass",
        dbname="testdb",
    ) as pg:
        yield pg


@pytest.fixture(scope="session")
def redis_container():
    """Start a Redis container for the test session."""
    if os.environ.get("REDIS_URL"):
        yield None
        return

    with RedisContainer(image="redis:7-alpine") as redis:
        yield redis


@pytest.fixture(scope="session")
def _set_env(postgres_container, redis_container):
    """Set environment variables from containers before importing app code.

    This must run before any app imports to ensure config.Settings picks up
    the test database URL instead of the default Docker Compose one.
    """
    if postgres_container is not None:
        host = postgres_container.get_container_host_ip()
        port = postgres_container.get_exposed_port(5432)
        async_url = f"postgresql+asyncpg://testuser:testpass@{host}:{port}/testdb"
        sync_url = f"postgresql://testuser:testpass@{host}:{port}/testdb"
        os.environ["DATABASE_URL"] = async_url
        os.environ["DATABASE_URL_SYNC"] = sync_url

    if redis_container is not None:
        host = redis_container.get_container_host_ip()
        port = redis_container.get_exposed_port(6379)
        os.environ["REDIS_URL"] = f"redis://{host}:{port}/0"


@pytest.fixture(scope="session")
def _run_migrations(_set_env):
    """Create pgvector extension and run Alembic migrations."""
    import sqlalchemy

    sync_url = os.environ.get("DATABASE_URL_SYNC") or os.environ["DATABASE_URL"].replace(
        "+asyncpg", ""
    )
    engine = sqlalchemy.create_engine(sync_url)

    with engine.connect() as conn:
        conn.execute(sqlalchemy.text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    engine.dispose()

    # Run Alembic migrations
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini"))
    alembic_cfg.set_main_option(
        "sqlalchemy.url",
        os.environ.get("DATABASE_URL_SYNC") or os.environ["DATABASE_URL"].replace("+asyncpg", ""),
    )
    command.upgrade(alembic_cfg, "head")


@pytest.fixture(scope="session")
def _app_setup(_run_migrations):
    """Import app code after environment is configured and migrations are run."""
    # Force re-import of config with new env vars by reloading
    import importlib

    import app.config

    importlib.reload(app.config)
    import app.core.database

    importlib.reload(app.core.database)


# ── Function-scoped fixtures ──────────────────────────────────────────


@pytest_asyncio.fixture(loop_scope="session")
async def db_session(_app_setup):
    """Provide an async session with SAVEPOINT isolation.

    Each test runs in a nested transaction that is rolled back after the test,
    keeping the database clean between tests.
    """
    from app.core.database import engine

    async with engine.connect() as conn:
        trans = await conn.begin()
        from sqlalchemy.ext.asyncio import AsyncSession

        session = AsyncSession(bind=conn, expire_on_commit=False)

        # Start a SAVEPOINT
        nested = await conn.begin_nested()

        yield session

        # Rollback SAVEPOINT and outer transaction
        await session.close()
        if nested.is_active:
            await nested.rollback()
        if trans.is_active:
            await trans.rollback()


@pytest_asyncio.fixture(loop_scope="session")
async def integration_client(db_session):
    """Async HTTP client wired to the real database via SAVEPOINT.

    Overrides get_session to return the test session so all API calls
    use the same transaction that gets rolled back.
    """
    import httpx

    from app.core.database import get_session
    from app.main import app

    async def override():
        yield db_session

    app.dependency_overrides[get_session] = override
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.clear()

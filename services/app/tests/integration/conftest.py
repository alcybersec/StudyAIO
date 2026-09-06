"""Integration test fixtures.

These tests run against a **real** Postgres (with pgvector) and a **real** Redis.
Both are addressed through environment variables that must already be exported
when the pytest process starts:

    DATABASE_URL        postgresql+asyncpg://<user>:<pass>@<host>:<port>/<db>
    DATABASE_URL_SYNC   postgresql://<user>:<pass>@<host>:<port>/<db>
    REDIS_URL           redis://<host>:<port>/0

`make test-integration` starts both services and exports all three for you.
CI does the same thing with service containers and a job-level `env:` block, so
local runs and CI take exactly the same code path.

Why the environment must be set *before* pytest starts
------------------------------------------------------
`app.config.settings` is a module-level singleton that reads the environment
once, at first import. `app.core.database.engine` and `app.core.redis.redis_client`
are built at *their* import time from that singleton. By the time any fixture
runs, both objects exist and are frozen against whatever the environment said
back then.

This conftest used to start testcontainers inside a session fixture and then
`importlib.reload()` `app.config` and `app.core.database` to make the app notice.
That never worked: reloading a module rebinds names *in that module*, not in the
dozen modules that already did `from app.core.database import async_session_factory`,
and the already-constructed engine keeps the URL it was created with. The app
stayed pointed at the compose default `db:5432`, a hostname that does not resolve
outside compose, so every test hung until it timed out (issue #56).

Rather than fight that, the fixtures now *verify* it: if the app's resolved
database URL does not match what the environment configured, the suite fails
immediately with an explanation instead of 35 opaque `TimeoutError`s.
"""

import os

import pytest
import pytest_asyncio

# ── Environment contract ─────────────────────────────────────────────

REQUIRED_ENV = ("DATABASE_URL", "DATABASE_URL_SYNC", "REDIS_URL")

_HOW_TO_RUN = """\
How to run the integration suite:

    make test-integration                 # starts Postgres + Redis, exports the
                                          # variables, runs pytest, cleans up

    # or point it at services you already have:
    DATABASE_URL=postgresql+asyncpg://user:pass@127.0.0.1:5432/testdb \\
    DATABASE_URL_SYNC=postgresql://user:pass@127.0.0.1:5432/testdb \\
    REDIS_URL=redis://127.0.0.1:6379/0 \\
    pytest tests/integration

The variables must be exported *before* pytest starts. Setting them from inside
a fixture is too late: app.config.settings, app.core.database.engine and
app.core.redis.redis_client are all built at import time (see this file's
module docstring, and issue #56)."""


def _redact(url: str) -> str:
    """Hide the password in a database URL before putting it in a message."""
    from sqlalchemy.engine import make_url

    try:
        return make_url(url).render_as_string(hide_password=True)
    except Exception:
        return url


@pytest.fixture(scope="session")
def _require_env() -> dict[str, str]:
    """Fail loudly, and early, when the suite has not been given its services."""
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            "Integration tests need a real Postgres and Redis, addressed by "
            "environment variables.\n\n"
            f"Missing: {', '.join(missing)}\n\n" + _HOW_TO_RUN
        )
    return {name: os.environ[name] for name in REQUIRED_ENV}


TEST_USER_ID = "00000000-0000-0000-0000-000000000099"


def _url_identity(url) -> tuple:
    """The parts of a URL that decide *which server and database* it reaches."""
    return (url.drivername, url.host, url.port, url.database, url.username)


@pytest.fixture(scope="session")
def _verify_app_wiring(_require_env):
    """Assert the app is actually wired to the database the fixtures prepared.

    This runs *before* migrations on purpose. `alembic/env.py` resolves the URL
    from `app.config.settings` itself, so a mis-wired app fails inside
    `command.upgrade()` — as a bare `TimeoutError` after a 60s hang against
    `db:5432`, with nothing to say the environment was the problem.
    """
    from sqlalchemy.engine import make_url

    from app.config import settings
    from app.core.database import engine

    expected = make_url(_require_env["DATABASE_URL"])
    actual = engine.url

    if _url_identity(expected) != _url_identity(actual):
        raise RuntimeError(
            "The application is not connected to the integration test database.\n\n"
            f"  DATABASE_URL says          : {expected.render_as_string(hide_password=True)}\n"
            f"  app.core.database.engine is: {actual.render_as_string(hide_password=True)}\n\n"
            "app.core.database builds its engine at import time from "
            "app.config.settings, which reads the environment once. If the engine "
            "above shows the compose default (host `db`), the environment was not "
            "set before pytest started — and `db` only resolves inside docker "
            "compose, so every test would hang until it timed out.\n\n" + _HOW_TO_RUN
        )

    # The Redis client is built at import time from the same settings object, so
    # it can drift the same way — and `redis:6379` hangs exactly like `db:5432`.
    if settings.redis_url != _require_env["REDIS_URL"]:
        raise RuntimeError(
            "The application is not connected to the integration test Redis.\n\n"
            f"  REDIS_URL says            : {_require_env['REDIS_URL']}\n"
            f"  app.config.settings says  : {settings.redis_url}\n\n" + _HOW_TO_RUN
        )


@pytest.fixture(scope="session")
def _run_migrations(_verify_app_wiring, _require_env):
    """Create the pgvector extension, run Alembic migrations, seed a test user."""
    import sqlalchemy

    sync_url = _require_env["DATABASE_URL_SYNC"]

    try:
        engine = sqlalchemy.create_engine(sync_url, connect_args={"connect_timeout": 10})
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        engine.dispose()
    except Exception as exc:
        raise RuntimeError(
            "Could not connect to the integration test database.\n\n"
            f"  DATABASE_URL_SYNC = {_redact(sync_url)}\n"
            f"  error             = {type(exc).__name__}: {exc}\n\n"
            "Is Postgres running and reachable at that address?\n\n" + _HOW_TO_RUN
        ) from exc

    from alembic import command
    from alembic.config import Config

    # No set_main_option here: alembic/env.py overwrites `sqlalchemy.url` with
    # `settings.database_url` when it is imported, and connects with its own
    # async engine. The migration target is therefore whatever the environment
    # said at import time — which _verify_app_wiring has already checked.
    alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini"))
    command.upgrade(alembic_cfg, "head")

    # Seed a test user for integration tests (multi-tenant FK requirement)
    engine2 = sqlalchemy.create_engine(sync_url)
    with engine2.connect() as conn:
        conn.execute(
            sqlalchemy.text(
                "INSERT INTO users (id, email, username, role, tier, is_active, email_verified, mfa_enabled) "
                "VALUES (:id, :email, :username, 'admin', 'free', true, false, false) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {
                "id": TEST_USER_ID,
                "email": "integration@test.local",
                "username": "integration_test",
            },
        )
        conn.commit()
    engine2.dispose()


@pytest.fixture(scope="session")
def test_user_id():
    """Return the ID of the seeded integration test user."""
    return TEST_USER_ID


# ── Function-scoped fixtures ──────────────────────────────────────────


@pytest_asyncio.fixture(loop_scope="session")
async def db_session(_run_migrations):
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
async def integration_client(db_session, test_user_id):
    """Async HTTP client wired to the real database via SAVEPOINT.

    Overrides get_session to return the test session and
    get_current_user_or_default to return the seeded test user.
    """
    import httpx

    from app.api.deps import get_current_user_or_default
    from app.core.database import get_session
    from app.main import app
    from app.models.user import User

    async def override_session():
        yield db_session

    # Build a User object matching the seeded row
    test_user = User(
        id=test_user_id,
        email="integration@test.local",
        username="integration_test",
        role="admin",
        tier="free",
        is_active=True,
        email_verified=False,
        mfa_enabled=False,
    )

    async def override_user(
        request=None,  # noqa: ARG001
        session=None,  # noqa: ARG001
    ):
        return test_user

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user_or_default] = override_user
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.clear()

"""The database connect timeout is bounded (GL#6).

asyncpg waits **60 seconds** to establish a connection by default. Two upload
endpoints open their own session outside the overridable `get_session`
dependency, so in the unit suite every one of their tests paid that minute:
`tests/unit/api/test_uploads.py` ran for minutes and under `-n 4` the whole
suite looked deadlocked. In CI the same stall is bounded but not free — it was a
large share of a `backend-tests` job that runs 977-1830s.

In production the same default means an unreachable database hangs every request
for a full minute before failing, which reads as a deadlock rather than an
outage.
"""

import pathlib
from unittest.mock import MagicMock, patch

import pytest

from app.config import settings


class TestConnectTimeoutIsBounded:
    def test_setting_exists_and_is_shorter_than_the_asyncpg_default(self):
        assert 0 < settings.db_connect_timeout < 60

    def test_the_engine_is_built_with_it(self):
        """Assert the wiring, not just the setting.

        A configured value nothing hands to the driver is the failure this
        guards: the setting would read as active while asyncpg kept its own
        60-second default.

        Loaded as a throwaway module rather than `importlib.reload`-ing the live
        one. Reloading swaps `app.core.database.engine` for a new object, which
        silently detaches the `do_connect` guard in `tests/unit/conftest.py` for
        every test that runs afterwards — this test used to break the two below
        it, and only in file order.
        """
        import importlib.util

        captured = {}

        def fake_create_async_engine(*args, **kwargs):
            captured.update(kwargs)
            return MagicMock()

        spec = importlib.util.spec_from_file_location(
            "throwaway_database_module",
            pathlib.Path(__file__).resolve().parents[3] / "app" / "core" / "database.py",
        )
        module = importlib.util.module_from_spec(spec)

        # Patch the *source*: executing the module runs
        # `from sqlalchemy.ext.asyncio import create_async_engine`, which would
        # otherwise rebind the real function over any patch on the module.
        with patch("sqlalchemy.ext.asyncio.create_async_engine", fake_create_async_engine):
            spec.loader.exec_module(module)

        assert "connect_args" in captured, "engine built without connect_args"
        assert captured["connect_args"]["timeout"] == settings.db_connect_timeout


class TestUnitTestsCannotOpenADatabase:
    """The autouse guard in `tests/unit/conftest.py`.

    It hooks SQLAlchemy's `do_connect` — the one moment a socket would be opened
    — so everything short of that is the real `AsyncSession` behaving normally.

    The first three attempts replaced the session with a hand-written stand-in
    and drew the line in the wrong place each time: refusing construction, then
    `commit`, then `flush`. None of those opens a connection, so each revision
    broke a test that was doing nothing wrong. These cases pin the boundary
    where it actually is.
    """

    async def test_building_a_session_is_allowed(self):
        """Sessions are lazy; constructing one opens nothing."""
        from app.core.database import async_session_factory

        async with async_session_factory() as session:
            assert session is not None

    async def test_committing_an_unused_session_is_allowed(self):
        """The case that broke `main`.

        `POST /api/auth/forgot-password` commits the session itself after the
        service it calls has been patched out. SQLAlchemy acquires no connection
        committing a session with nothing pending.
        """
        from app.core.database import async_session_factory

        async with async_session_factory() as session:
            await session.commit()
            await session.flush()
            await session.rollback()

    async def test_querying_is_refused(self):
        """The first operation that genuinely needs a socket."""
        from sqlalchemy import text

        from app.core.database import async_session_factory

        with pytest.raises(Exception) as exc:
            async with async_session_factory() as session:
                await session.execute(text("SELECT 1"))

        assert "unit test" in str(exc.value).lower()

    async def test_the_uploads_bypass_is_covered(self):
        """`app/api/uploads.py` imports the factory directly and opens its own
        session to award XP — the bypass that caused GL#6.

        The engine-level hook covers it without patching that binding, which the
        factory-level versions of this guard had to do separately.
        """
        from sqlalchemy import text

        from app.api import uploads

        with pytest.raises(Exception) as exc:
            async with uploads.async_session_factory() as session:
                await session.execute(text("SELECT 1"))

        assert "unit test" in str(exc.value).lower()

    async def test_it_fails_fast_rather_than_waiting_out_a_timeout(self):
        """The point of the whole exercise: no 60-second stall."""
        import time

        from sqlalchemy import text

        from app.core.database import async_session_factory

        started = time.monotonic()
        with pytest.raises(RuntimeError):
            async with async_session_factory() as session:
                await session.execute(text("SELECT 1"))

        assert time.monotonic() - started < 5

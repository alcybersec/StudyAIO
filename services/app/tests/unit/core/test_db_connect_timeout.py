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

import importlib
from unittest.mock import MagicMock, patch

import pytest

from app.config import settings


class TestConnectTimeoutIsBounded:
    def test_setting_exists_and_is_shorter_than_the_asyncpg_default(self):
        assert 0 < settings.db_connect_timeout < 60

    def test_the_engine_is_built_with_it(self):
        """Assert the wiring, not just the setting.

        A configured value nothing passes to the driver is the failure this
        guards: the setting would read as active while asyncpg kept its own
        60-second default.
        """
        captured = {}

        def fake_create_async_engine(*args, **kwargs):
            captured.update(kwargs)
            return MagicMock()

        # Patch the *source* module: reloading re-executes
        # `from sqlalchemy.ext.asyncio import create_async_engine`, which would
        # rebind the real function over a patch applied to `app.core.database`.
        with patch("sqlalchemy.ext.asyncio.create_async_engine", fake_create_async_engine):
            importlib.reload(importlib.import_module("app.core.database"))

        try:
            assert "connect_args" in captured, "engine built without connect_args"
            assert captured["connect_args"]["timeout"] == settings.db_connect_timeout
        finally:
            # Leave the real engine in place for everything after this test.
            importlib.reload(importlib.import_module("app.core.database"))


class TestUnitTestsCannotOpenADatabase:
    """The autouse guard in `tests/unit/conftest.py`.

    It refuses a session's *use*, not its construction. SQLAlchemy sessions are
    lazy — `async_session_factory()` opens no socket — so `get_session` building
    one and handing it to an endpoint that never touches it must keep working.
    An earlier version refused construction and broke
    `test_rate_limit_returns_429`, where the service is patched and the session
    is never used. CI caught that; a local `-n 4` run did not.
    """

    async def test_building_a_session_is_allowed(self):
        """The case the first version of this guard got wrong."""
        from app.core.database import async_session_factory

        async with async_session_factory() as session:
            assert session is not None

    async def test_using_one_is_refused(self):
        from app.core.database import async_session_factory

        with pytest.raises(Exception) as exc:
            async with async_session_factory() as session:
                await session.execute("SELECT 1")

        assert "unit test" in str(exc.value).lower()

    async def test_the_uploads_module_binding_is_patched_too(self):
        """`app.api.uploads` imports the name, so it holds a second reference.

        Patching only `app.core.database` would leave the endpoint that actually
        caused this — awarding upload XP through its own session — reaching the
        real factory.
        """
        from app.api import uploads

        with pytest.raises(Exception) as exc:
            async with uploads.async_session_factory() as session:
                await session.execute("SELECT 1")

        assert "unit test" in str(exc.value).lower()

    async def test_teardown_operations_stay_silent(self):
        """`close`/`rollback` run on the way out and touch no database."""
        from app.core.database import async_session_factory

        async with async_session_factory() as session:
            session.add(object())
            await session.rollback()
            await session.close()

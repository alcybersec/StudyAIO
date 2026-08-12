"""Tests for the async/sync bridge used by Celery tasks."""

from unittest.mock import MagicMock, patch

from app.core.database import run_async


class TestRunAsync:
    """Tests for run_async()."""

    def test_returns_coroutine_result(self):
        """The coroutine runs to completion and its value is returned."""

        async def coro():
            return 42

        with patch("app.core.database.engine") as mock_engine:
            mock_engine.sync_engine = MagicMock()
            assert run_async(coro()) == 42

    def test_pool_is_dropped_without_closing_connections(self):
        """Stale connections are abandoned, not closed.

        Closing them would await on asyncpg from outside a greenlet context —
        the connections belong to an event loop that is already gone — which
        SQLAlchemy logs as MissingGreenlet on every task. dispose(close=False)
        swaps in a fresh pool instead.
        """

        async def coro():
            return None

        with patch("app.core.database.engine") as mock_engine:
            mock_engine.sync_engine = MagicMock()
            run_async(coro())

        mock_engine.sync_engine.dispose.assert_called_once_with(close=False)

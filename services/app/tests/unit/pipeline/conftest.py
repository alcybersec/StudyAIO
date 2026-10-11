"""Pipeline unit-test fixtures."""

import contextlib
from unittest.mock import patch

import pytest


@contextlib.asynccontextmanager
async def _no_lock(*args, **kwargs):
    yield


@pytest.fixture(autouse=True)
def _no_week_lock():
    """Summarize's Postgres advisory lock needs a database; unit tests stub it.

    `test_summarize_week_lock.py` exercises the real lock against a fake
    connection via `REAL_WEEK_LOCK`.
    """
    with patch("app.pipeline.summarize._week_lock", _no_lock):
        yield

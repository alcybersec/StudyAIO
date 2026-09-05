"""Tests for the startup check that reports an unusable embedding provider.

Issue #44: the api container runs as `studyaio`, whose home is the root-owned
`/app`, so sentence-transformers could not create its model cache. `/api/qa`
returned 500 and chat silently answered with no lecture context — for six
months, with nothing in the log at startup to say so. These tests pin the
signal that would have caught it on day one.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.main import warn_if_embedding_provider_unavailable


@pytest.fixture
def logged():
    """Capture the check's log calls."""
    with patch("app.main.logger") as mock_logger:
        yield mock_logger


def _errors(mock_logger):
    return [
        c
        for c in mock_logger.error.call_args_list
        if c.args[:1] == ("embedding_provider_unavailable",)
    ]


def _ready(mock_logger):
    return [
        c for c in mock_logger.info.call_args_list if c.args[:1] == ("embedding_provider_ready",)
    ]


def _provider(preload_error: Exception | None = None) -> MagicMock:
    provider = MagicMock()
    provider.dimensions = 384
    if preload_error is not None:
        provider.preload.side_effect = preload_error
    return provider


def test_reports_the_permission_error_that_broke_production(logged):
    """The exact production shape: the cache directory cannot be created."""
    provider = _provider(PermissionError(13, "Permission denied", "/app/.cache"))

    with patch("app.main.get_embedding_provider", return_value=provider):
        warn_if_embedding_provider_unavailable()

    errors = _errors(logged)
    assert errors, "an unloadable model must be logged at error level"
    assert errors[0].kwargs["error_type"] == "PermissionError"
    assert not _ready(logged)


def test_reports_a_provider_that_cannot_be_constructed(logged):
    """A misconfigured backend fails before there is a provider to preload."""
    with patch(
        "app.main.get_embedding_provider",
        side_effect=RuntimeError("EMBEDDING_DIMENSIONS disagrees with the column"),
    ):
        warn_if_embedding_provider_unavailable()

    assert _errors(logged)


def test_does_not_raise_so_the_app_still_starts(logged):
    """A self-hosted instance with no model must still boot and serve.

    The check is a signal, not a gate. If it ever raises, removing the model
    takes the whole API down with it.
    """
    with patch("app.main.get_embedding_provider", side_effect=OSError("no model")):
        warn_if_embedding_provider_unavailable()  # must not raise


def test_silent_and_ready_when_the_model_loads(logged):
    provider = _provider()

    with patch("app.main.get_embedding_provider", return_value=provider):
        warn_if_embedding_provider_unavailable()

    assert not _errors(logged)
    assert _ready(logged)


def test_the_model_is_loaded_not_merely_constructed(logged):
    """`preload()` must be called — construction on its own proves nothing.

    `SentenceTransformerProvider.__init__` records a model name and returns
    without touching the filesystem. A check that stopped at
    `get_embedding_provider()` would have passed happily through the entire
    six-month outage, which is the failure this test exists to prevent.
    """
    provider = _provider()

    with patch("app.main.get_embedding_provider", return_value=provider):
        warn_if_embedding_provider_unavailable()

    provider.preload.assert_called_once_with()


@pytest.mark.asyncio
async def test_startup_actually_runs_the_check():
    """The check must be wired into the lifespan, not merely defined.

    Without this the suite passes with the call deleted from startup — the
    check exists and never runs, which is exactly the shape of the bug.
    """
    from app.main import app, lifespan

    with (
        patch("app.main.warn_if_embedding_provider_unavailable") as check,
        patch("app.main.configure_logging"),
    ):
        async with lifespan(app):
            pass

    check.assert_called_once()

"""Tests for the startup warning about untrusted proxy headers.

Uvicorn discards `X-Forwarded-For` unless the immediate peer is named in
`FORWARDED_ALLOW_IPS`. Behind a proxy on another host that means every request
arrives as the proxy's address, so the rate limiter puts the whole internet in
one bucket and the access log attributes nothing (issue #39). The app cannot
fix that itself — the correct value is deployment-specific — but it must not
stay silent about it.
"""

from unittest.mock import patch

import pytest

from app.main import warn_if_proxy_headers_untrusted


@pytest.fixture
def warned(monkeypatch):
    """Capture `logger.warning` calls from the check."""
    with patch("app.main.logger") as mock_logger:
        yield mock_logger


def _warnings(mock_logger):
    return [
        c for c in mock_logger.warning.call_args_list if c.args[:1] == ("proxy_headers_untrusted",)
    ]


def test_warns_when_unset_in_saas_mode(warned, monkeypatch):
    monkeypatch.setattr("app.main.settings.self_hosted", False)
    monkeypatch.delenv("FORWARDED_ALLOW_IPS", raising=False)

    warn_if_proxy_headers_untrusted()

    assert _warnings(warned), "an unset FORWARDED_ALLOW_IPS must warn"


def test_warns_when_left_at_the_uvicorn_default(warned, monkeypatch):
    """127.0.0.1 is the default, and is wrong for any proxy on another host."""
    monkeypatch.setattr("app.main.settings.self_hosted", False)
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "127.0.0.1")

    warn_if_proxy_headers_untrusted()

    assert _warnings(warned)


def test_silent_when_a_proxy_is_named(warned, monkeypatch):
    monkeypatch.setattr("app.main.settings.self_hosted", False)
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "192.0.2.10")

    warn_if_proxy_headers_untrusted()

    assert not _warnings(warned)


def test_silent_in_self_hosted_mode(warned, monkeypatch):
    """A self-hosted instance is usually reached directly; the warning is noise."""
    monkeypatch.setattr("app.main.settings.self_hosted", True)
    monkeypatch.delenv("FORWARDED_ALLOW_IPS", raising=False)

    warn_if_proxy_headers_untrusted()

    assert not _warnings(warned)


def test_whitespace_only_value_still_warns(warned, monkeypatch):
    """An empty-but-present variable is as untrusted as an absent one."""
    monkeypatch.setattr("app.main.settings.self_hosted", False)
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "   ")

    warn_if_proxy_headers_untrusted()

    assert _warnings(warned)


@pytest.mark.asyncio
async def test_startup_actually_runs_the_check():
    """The check must be wired into the lifespan, not merely defined.

    Without this the suite passes with the call deleted from startup — the
    warning exists and never fires, which is the failure it is meant to
    prevent.
    """
    from app.main import app, lifespan

    with (
        patch("app.main.warn_if_proxy_headers_untrusted") as check,
        # Stubbed because it loads the embedding model for real; its own wiring
        # test lives in test_embedding_startup_check.py.
        patch("app.main.warn_if_embedding_provider_unavailable"),
    ):
        async with lifespan(app):
            pass

    check.assert_called_once()

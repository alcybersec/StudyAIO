"""Unit tests for client-address attribution in the access log.

The access log records the client address so authentication failures can be
attributed and a brute-force attempt is visible at all. The value must be the
same one the rate limiter keys on, or a 429 in the log cannot be traced back to
the address that earned it.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from slowapi.util import get_remote_address

from app.main import client_ip


def _request(host: str | None, headers: dict[str, str] | None = None):
    """Build the smallest object `client_ip` and `get_remote_address` accept."""
    return SimpleNamespace(
        client=None if host is None else SimpleNamespace(host=host),
        headers=headers or {},
    )


def test_client_ip_is_the_transport_address():
    assert client_ip(_request("203.0.113.10")) == "203.0.113.10"


def test_client_ip_agrees_with_the_rate_limiter():
    """The log and the limiter must name the same address.

    If these diverge, a 429 cannot be attributed: the limiter blocks one
    address while the log records another.
    """
    request = _request("203.0.113.10")
    assert client_ip(request) == get_remote_address(request)


def test_forged_forwarding_headers_are_ignored():
    """A client-supplied header must not decide what gets logged.

    `request.client` is what the ASGI proxy-header layer resolved against the
    trusted hops. Reading the raw header here would log whatever an attacker
    put in it and would disagree with the limiter.
    """
    request = _request(
        "203.0.113.10",
        headers={
            "X-Forwarded-For": "198.51.100.1",
            "X-Real-IP": "198.51.100.2",
            "True-Client-IP": "198.51.100.3",
            "Forwarded": "for=198.51.100.4",
        },
    )
    assert client_ip(request) == "203.0.113.10"


def test_missing_client_is_reported_as_unknown():
    """Some ASGI servers and in-process test clients leave `client` unset."""
    assert client_ip(_request(None)) == "unknown"


def test_blank_client_host_is_reported_as_unknown():
    assert client_ip(_request("")) == "unknown"


def _http_request_entries(mock_logger):
    """The `http_request` entries the middleware emitted."""
    return [c for c in mock_logger.info.call_args_list if c.args and c.args[0] == "http_request"]


@pytest.mark.asyncio
async def test_access_log_records_the_client_address(async_client):
    """The middleware must actually put it in the log entry."""
    with patch("app.main.logger") as mock_logger:
        await async_client.get("/api/auth/config")

    entries = _http_request_entries(mock_logger)
    assert entries, "no http_request entry was logged"
    assert "client_ip" in entries[0].kwargs


@pytest.mark.asyncio
async def test_health_checks_are_still_skipped(async_client):
    """Health probes stay out of the log — they would drown the real traffic."""
    with patch("app.main.logger") as mock_logger:
        await async_client.get("/health")

    assert not _http_request_entries(mock_logger)

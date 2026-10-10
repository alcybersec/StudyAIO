"""Transient vs permanent AI error classification (TECH-04, GL#22)."""

import httpx
import pytest

from app.agents.transient import TransientAgentError, is_transient_error, is_transient_text
from app.core.exceptions import AgentError


class _StatusError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"status {status_code}")
        self.status_code = status_code


class APITimeoutError(Exception):
    """Named like the SDK classes; the classifier matches on class name."""


class RateLimitError(Exception):
    pass


@pytest.mark.parametrize("code", [408, 425, 429, 500, 502, 503, 504, 529])
def test_transient_status_codes(code):
    assert is_transient_error(_StatusError(code))


@pytest.mark.parametrize("code", [400, 401, 403, 404, 422])
def test_permanent_status_codes(code):
    assert not is_transient_error(_StatusError(code))


@pytest.mark.parametrize(
    "exc",
    [
        TimeoutError(),
        ConnectionResetError(),
        ConnectionError(),
        httpx.ConnectTimeout("x"),
        httpx.ReadError("x"),
        APITimeoutError(),
        RateLimitError(),
    ],
)
def test_transient_exception_types(exc):
    assert is_transient_error(exc)


@pytest.mark.parametrize("exc", [ValueError("bad"), KeyError("k"), RuntimeError("boom")])
def test_other_exceptions_are_permanent(exc):
    assert not is_transient_error(exc)


@pytest.mark.parametrize(
    "text",
    [
        "API Error: 429 rate limit exceeded",
        "529 overloaded_error",
        "503 Service Unavailable",
        "read ECONNRESET",
        "Connection reset by peer",
    ],
)
def test_transient_cli_text(text):
    assert is_transient_text(text)


@pytest.mark.parametrize("text", ["401 OAuth token revoked", "invalid prompt", ""])
def test_permanent_cli_text(text):
    assert not is_transient_text(text)


def test_transient_error_is_agent_error():
    assert issubclass(TransientAgentError, AgentError)


def test_adapter_builds_transient_error_and_redacts():
    from app.agents.anthropic_api import AnthropicAPIAdapter

    adapter = AnthropicAPIAdapter(api_key="sk-secret-value-123")
    err = adapter._agent_error("failed sk-secret-value-123", _StatusError(503))
    assert isinstance(err, TransientAgentError)
    assert "sk-secret-value-123" not in str(err)


def test_adapter_builds_permanent_error_for_auth():
    from app.agents.anthropic_api import AnthropicAPIAdapter

    err = AnthropicAPIAdapter(api_key="k")._agent_error("nope", _StatusError(401))
    assert type(err) is AgentError


def test_adapter_without_cause_is_permanent():
    from app.agents.anthropic_api import AnthropicAPIAdapter

    assert type(AnthropicAPIAdapter(api_key="k")._agent_error("x")) is AgentError

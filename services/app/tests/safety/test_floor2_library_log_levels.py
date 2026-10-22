"""Floor 2 (credentials out of logs): third-party loggers and settings errors (SEC-015 follow-up).

SEC-015 finding F1 was httpx's own ``INFO`` request line, which prints the full
Telegram URL and so the bot token. ``configure_logging`` now caps the libraries
that print request URLs at ``WARNING`` whatever the root level. ``LOG_LEVEL`` is a
documented operator knob (``.env.example``, ``docs/deployment.md``), so the caps
are checked with the root logger at ``DEBUG``, the worst case an operator can
choose.

Pins:

* the capped set (``httpx``, ``httpcore``, ``googleapiclient``, ``stripe``) stays
  at ``WARNING`` or above after ``configure_logging("DEBUG")``;
* a per-user AI key handed to the OpenAI and Anthropic adapters never reaches the
  log stream at ``DEBUG``, on success or on a provider rejection;
* a ``Settings`` validation error never echoes the rejected value of any
  ``SecretStr`` setting, whether passed directly or read from the environment.

Finding F2 (fixed in ``5e1eda8``, plain test since): at ``DEBUG``,
``requests_oauthlib`` logs the Google token request body (client secret, auth code)
and the obtained token (the user's refresh token); ``botocore`` logs the signed
request headers, including ``X-Amz-Security-Token`` when the credentials are
temporary; ``urllib3`` logs request paths (a Web Push endpoint path is a
capability). ``configure_logging`` now caps ``requests_oauthlib``, ``oauthlib``,
``botocore``, ``boto3`` and ``urllib3`` as well, and
``test_floor2_credential_logging_libraries_capped_at_warning`` holds that.
"""

from __future__ import annotations

import io
import logging
from unittest.mock import patch

import pytest
import structlog
from pydantic import SecretStr, ValidationError

AI_KEY = "sk-floor2-ai-key-7c4e1d9b2a6f40e8b3c5d7e9f1a2b4c6"
# Short on purpose: pydantic elides the middle of a long input_value, so a long
# probe would pass a leaking error vacuously.
PROBE = "f2pr0be7"

CAPPED = ("httpx", "httpcore", "googleapiclient", "stripe")
# F2: credential-bearing at DEBUG only; capped since 5e1eda8 (module docstring).
F2_CAPPED = ("requests_oauthlib", "oauthlib", "botocore", "boto3", "urllib3")


@pytest.fixture
def stream():
    """The app's real logging configuration at DEBUG on a fresh root handler; restored after."""
    from app.core.logging import configure_logging

    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    saved_config = structlog.get_config()
    names = CAPPED + F2_CAPPED
    saved_levels = {n: logging.getLogger(n).level for n in names}
    out = io.StringIO()
    root.handlers = [logging.StreamHandler(out)]
    try:
        # Start from "nobody capped anything" so a pass is configure_logging's doing.
        for n in names:
            logging.getLogger(n).setLevel(logging.NOTSET)
        configure_logging("DEBUG")
        root.setLevel(logging.DEBUG)
        yield out
    finally:
        root.handlers = saved_handlers
        root.setLevel(saved_level)
        structlog.configure(**saved_config)
        for n, level in saved_levels.items():
            logging.getLogger(n).setLevel(level)


# --------------------------------------------------------------------------- caps


@pytest.mark.parametrize("name", CAPPED)
def test_floor2_url_logging_library_capped_at_warning(stream, name):
    assert logging.getLogger(name).getEffectiveLevel() >= logging.WARNING, (
        f"{name} logs full request URLs below WARNING; configure_logging must cap it"
    )


def test_floor2_credential_logging_libraries_capped_at_warning(stream):
    low = [n for n in F2_CAPPED if logging.getLogger(n).getEffectiveLevel() < logging.WARNING]
    assert not low, f"credential-bearing DEBUG loggers not capped: {low}"


# ------------------------------------------------------------- per-user AI keys


def _openai_transport(seen: list, status: int):
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("authorization", ""))
        if status != 200:
            return httpx.Response(status, json={"error": {"message": "bad key", "type": "x"}})
        return httpx.Response(
            200,
            json={
                "id": "c1",
                "object": "chat.completion",
                "created": 0,
                "model": "gpt-x",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "ok"},
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [200, 401], ids=["ok", "rejected"])
async def test_floor2_openai_adapter_logs_no_user_key_at_debug(stream, status):
    import httpx

    from app.agents.openai_adapter import OpenAIAdapter
    from app.core.exceptions import AgentError

    seen: list[str] = []

    def client(**kw):
        return httpx.AsyncClient(transport=_openai_transport(seen, status), **kw)

    adapter = OpenAIAdapter(api_key=AI_KEY, model="gpt-x")
    with patch("app.agents.openai_adapter.DefaultAsyncHttpxClient", side_effect=client):
        if status == 200:
            assert await adapter._call_api("hello") == "ok"
        else:
            with pytest.raises(AgentError):
                await adapter._call_api("hello")
    assert seen and AI_KEY in seen[0], "the key never reached the transport; the pin is vacuous"
    text = stream.getvalue()
    assert "openai_api_call" in text, text
    assert AI_KEY not in text, "a per-user OpenAI key reached the log"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [200, 401], ids=["ok", "rejected"])
async def test_floor2_anthropic_adapter_logs_no_user_key_at_debug(stream, status):
    import httpx
    from anthropic import AsyncAnthropic

    from app.agents.anthropic_api import AnthropicAPIAdapter
    from app.core.exceptions import AgentError

    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("x-api-key", ""))
        if status != 200:
            return httpx.Response(
                401, json={"type": "error", "error": {"type": "authentication_error"}}
            )
        return httpx.Response(
            200,
            json={
                "id": "m1",
                "type": "message",
                "role": "assistant",
                "model": "claude-x",
                "content": [{"type": "text", "text": "ok"}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    def make(**kw):
        return AsyncAnthropic(
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            max_retries=0,
            **kw,
        )

    adapter = AnthropicAPIAdapter(api_key=AI_KEY, model="claude-x")
    with patch("app.agents.anthropic_api.AsyncAnthropic", side_effect=make):
        if status == 200:
            assert await adapter._call_api("hello") == "ok"
        else:
            with pytest.raises(AgentError):
                await adapter._call_api("hello")
    assert seen and seen[0] == AI_KEY, "the key never reached the transport; the pin is vacuous"
    text = stream.getvalue()
    assert "anthropic_api_call" in text, text
    assert AI_KEY not in text, "a per-user Anthropic key reached the log"


# ------------------------------------------------------- settings validation


def _secret_fields() -> list[str]:
    from app.config import Settings

    return [n for n, f in Settings.model_fields.items() if f.annotation is SecretStr]


def test_floor2_settings_has_secret_fields():
    """Guards the parametrisation below against silently collecting nothing."""
    assert "telegram_webhook_secret" in _secret_fields()
    assert len(_secret_fields()) >= 10


@pytest.mark.parametrize("field", _secret_fields())
def test_floor2_settings_error_never_echoes_a_secret_value(field):
    from app.config import Settings

    # A non-string is refused by SecretStr itself, so every secret field is exercised.
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None, **{field: {"value": PROBE}})
    for text in (str(exc.value), repr(exc.value)):
        assert field in text, text
        assert PROBE not in text, f"a ValidationError echoed the value of {field}"


def test_floor2_settings_error_from_env_never_echoes_the_webhook_secret(monkeypatch):
    from app.config import Settings

    bad = f"{PROBE} !"
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", bad)
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None)
    for text in (str(exc.value), repr(exc.value)):
        assert "TELEGRAM_WEBHOOK_SECRET" in text, text
        assert PROBE not in text, "a ValidationError echoed the webhook secret from the env"

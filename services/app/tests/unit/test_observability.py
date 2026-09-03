"""Unit tests for Sentry error monitoring wiring.

`sentry_sdk` is an optional dependency, so these tests inject a fake module
rather than importing the real one — the wiring must be verifiable without it
installed, and must degrade to a no-op when it is missing.
"""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock
from urllib.parse import parse_qsl

import pytest

from app.config import settings
from app.core import observability

# Deliberately not in Sentry's scheme://key@host/id form: a realistic-looking
# DSN in the repo trips secret scanners for no benefit. init_sentry only
# requires a non-empty string, and the SDK itself is mocked here.
FAKE_DSN = "sentry-dsn-placeholder"


@pytest.fixture
def fake_sentry(monkeypatch):
    """Install a stub `sentry_sdk` (plus integrations) into sys.modules."""
    sdk = MagicMock()

    fastapi_mod = SimpleNamespace(FastApiIntegration=MagicMock(return_value="fastapi-int"))
    starlette_mod = SimpleNamespace(StarletteIntegration=MagicMock(return_value="starlette-int"))
    celery_mod = SimpleNamespace(CeleryIntegration=MagicMock(return_value="celery-int"))
    logging_mod = SimpleNamespace(LoggingIntegration=MagicMock(return_value="logging-int"))

    monkeypatch.setitem(sys.modules, "sentry_sdk", sdk)
    monkeypatch.setitem(sys.modules, "sentry_sdk.integrations.fastapi", fastapi_mod)
    monkeypatch.setitem(sys.modules, "sentry_sdk.integrations.starlette", starlette_mod)
    monkeypatch.setitem(sys.modules, "sentry_sdk.integrations.celery", celery_mod)
    monkeypatch.setitem(sys.modules, "sentry_sdk.integrations.logging", logging_mod)
    return sdk


@pytest.fixture(autouse=True)
def reset_init_flag():
    observability._initialized = False
    yield
    observability._initialized = False


class TestInitSentryDisabled:
    """With no DSN configured, Sentry must stay completely inert."""

    def test_returns_false_when_dsn_empty(self, monkeypatch, fake_sentry):
        monkeypatch.setattr(settings, "sentry_dsn", "", raising=False)
        assert observability.init_sentry("api") is False
        fake_sentry.init.assert_not_called()

    def test_returns_false_when_dsn_whitespace(self, monkeypatch, fake_sentry):
        monkeypatch.setattr(settings, "sentry_dsn", "   ", raising=False)
        assert observability.init_sentry("api") is False
        fake_sentry.init.assert_not_called()

    def test_returns_false_when_sdk_not_installed(self, monkeypatch):
        monkeypatch.setattr(settings, "sentry_dsn", FAKE_DSN, raising=False)
        # Simulate the package being absent.
        monkeypatch.setitem(sys.modules, "sentry_sdk", None)
        assert observability.init_sentry("api") is False


class TestInitSentryEnabled:
    """With a DSN set, the SDK is configured with safe defaults."""

    @pytest.fixture(autouse=True)
    def _dsn(self, monkeypatch):
        monkeypatch.setattr(settings, "sentry_dsn", FAKE_DSN, raising=False)
        monkeypatch.setattr(settings, "sentry_environment", "beta", raising=False)
        monkeypatch.setattr(settings, "sentry_traces_sample_rate", 0.25, raising=False)
        monkeypatch.setattr(settings, "sentry_release", "studyaio@1.2.3", raising=False)

    def test_returns_true_and_inits(self, fake_sentry):
        assert observability.init_sentry("api") is True
        fake_sentry.init.assert_called_once()

    def test_never_sends_pii(self, fake_sentry):
        observability.init_sentry("api")
        kwargs = fake_sentry.init.call_args.kwargs
        assert kwargs["send_default_pii"] is False

    def test_passes_environment_release_and_sample_rate(self, fake_sentry):
        observability.init_sentry("api")
        kwargs = fake_sentry.init.call_args.kwargs
        assert kwargs["dsn"] == FAKE_DSN
        assert kwargs["environment"] == "beta"
        assert kwargs["release"] == "studyaio@1.2.3"
        assert kwargs["traces_sample_rate"] == 0.25

    def test_api_component_uses_fastapi_integrations(self, fake_sentry):
        observability.init_sentry("api")
        integrations = fake_sentry.init.call_args.kwargs["integrations"]
        assert "fastapi-int" in integrations
        assert "starlette-int" in integrations
        assert "celery-int" not in integrations

    def test_worker_component_uses_celery_integration(self, fake_sentry):
        observability.init_sentry("worker")
        integrations = fake_sentry.init.call_args.kwargs["integrations"]
        assert "celery-int" in integrations
        assert "fastapi-int" not in integrations

    def test_tags_the_component(self, fake_sentry):
        observability.init_sentry("worker")
        fake_sentry.set_tag.assert_any_call("component", "worker")

    def test_is_idempotent(self, fake_sentry):
        assert observability.init_sentry("api") is True
        assert observability.init_sentry("api") is True
        fake_sentry.init.assert_called_once()

    def test_init_failure_is_swallowed(self, monkeypatch, fake_sentry):
        fake_sentry.init.side_effect = RuntimeError("bad dsn")
        # Monitoring must never take the process down with it.
        assert observability.init_sentry("api") is False


class TestScrubEvent:
    """Credentials must never reach Sentry."""

    def test_scrubs_sensitive_headers(self):
        event = {
            "request": {
                "headers": {
                    "Authorization": "Bearer secret-token",
                    "Cookie": "access_token=abc",
                    "User-Agent": "pytest",
                }
            }
        }
        out = observability.scrub_event(event, {})
        headers = out["request"]["headers"]
        assert headers["Authorization"] == "[Filtered]"
        assert headers["Cookie"] == "[Filtered]"
        assert headers["User-Agent"] == "pytest"

    def test_drops_cookies_entirely(self):
        event = {"request": {"cookies": {"access_token": "abc"}}}
        out = observability.scrub_event(event, {})
        assert "cookies" not in out["request"]

    def test_scrubs_token_query_params(self):
        """Reset and verification links carry a bearer token in the URL."""
        event = {
            "request": {
                "url": "https://app.test/reset-password",
                "query_string": "token=super-secret&next=/home",
            }
        }
        out = observability.scrub_event(event, {})
        scrubbed = out["request"]["query_string"]
        assert "super-secret" not in scrubbed
        # Non-sensitive params survive (re-encoded, so compare parsed pairs).
        assert dict(parse_qsl(scrubbed))["next"] == "/home"

    def test_scrubs_token_in_url_query(self):
        event = {"request": {"url": "https://app.test/verify-email?token=super-secret"}}
        out = observability.scrub_event(event, {})
        assert "super-secret" not in out["request"]["url"]

    def test_scrubs_sensitive_extra_keys(self):
        event = {"extra": {"password": "hunter2", "invite_code": "BETA-1", "week": 5}}
        out = observability.scrub_event(event, {})
        assert out["extra"]["password"] == "[Filtered]"
        assert out["extra"]["invite_code"] == "[Filtered]"
        assert out["extra"]["week"] == 5

    def test_handles_missing_request(self):
        assert observability.scrub_event({}, {}) == {}

    def test_handles_malformed_event(self):
        """A scrubber that raises would drop the event; it must not raise."""
        event = {"request": "not-a-dict", "extra": None}
        assert observability.scrub_event(event, {}) is not None

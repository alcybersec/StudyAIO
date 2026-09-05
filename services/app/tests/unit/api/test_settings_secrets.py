"""Regression guard for #30 — GET /api/settings must never return a credential.

The bug: `SettingsResponse` carried the provider keys as plain strings and
`settings_service` populated them from the instance configuration, so any
authenticated account read the operator's key verbatim. These tests assert
the response carries booleans only, for an ordinary user *and* for an admin.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from app.config import settings as app_settings

# Deliberately unlike a real credential — the repository is scanned for secrets.
INSTANCE_ZAI_KEY = "<test-placeholder>-instance-zai-key"
INSTANCE_ANTHROPIC_KEY = "<test-placeholder>-instance-anthropic-key"
USER_ZAI_KEY = "<test-placeholder>-user-zai-key"

SECRET_FIELDS = (
    "anthropic_api_key",
    "openai_api_key",
    "zai_api_key",
    "claude_cli_credentials",
)


@pytest.fixture
def instance_credentials():
    """Configure instance-level provider credentials, as a deployment would."""
    with (
        patch.object(app_settings, "zai_api_key", SecretStr(INSTANCE_ZAI_KEY)),
        patch.object(app_settings, "anthropic_api_key", SecretStr(INSTANCE_ANTHROPIC_KEY)),
        patch.object(app_settings, "agent_backend", "zai"),
    ):
        yield


def _stub_user_settings(overrides: dict | None = None) -> MagicMock:
    stub = MagicMock()
    stub.settings_json = overrides or {}
    stub.theme = "system"
    stub.dashboard_layout = None
    return stub


def _assert_no_secrets(body: str, data: dict) -> None:
    assert INSTANCE_ZAI_KEY not in body
    assert INSTANCE_ANTHROPIC_KEY not in body
    assert USER_ZAI_KEY not in body
    for field in SECRET_FIELDS:
        assert field not in data, f"{field} must not be returned"
        flag = f"{field}_configured"
        assert flag in data, f"{flag} missing"
        assert isinstance(data[flag], bool)


@pytest.mark.asyncio
class TestSettingsNeverReturnSecrets:
    """No caller — user or admin — reads a credential back."""

    async def test_plain_user_gets_no_credentials(
        self, async_client, instance_credentials, make_user
    ):
        """A role=user, tier=free account never receives the instance key."""
        from app.api.deps import get_current_user_or_default
        from app.main import app

        plain = make_user(id="user-plain", role="user", tier="free")
        app.dependency_overrides[get_current_user_or_default] = lambda: plain

        with patch(
            "app.services.settings_service._get_or_create_user_settings",
            new_callable=AsyncMock,
            return_value=_stub_user_settings(),
        ):
            response = await async_client.get("/api/settings")

        assert response.status_code == 200
        _assert_no_secrets(response.text, response.json())

    async def test_admin_gets_no_credentials(self, async_client, instance_credentials):
        """Admins get no secrets either — the instance key is env-configured."""
        with patch(
            "app.services.settings_service._get_or_create_user_settings",
            new_callable=AsyncMock,
            return_value=_stub_user_settings(),
        ):
            response = await async_client.get("/api/settings")

        assert response.status_code == 200
        _assert_no_secrets(response.text, response.json())

    async def test_configured_flag_reflects_the_users_own_key(
        self, async_client, instance_credentials, make_user
    ):
        """The boolean tracks the user's own stored credential, not the instance one."""
        from app.api.deps import get_current_user_or_default
        from app.main import app

        plain = make_user(id="user-plain", role="user", tier="free")
        app.dependency_overrides[get_current_user_or_default] = lambda: plain

        with patch(
            "app.services.settings_service._get_or_create_user_settings",
            new_callable=AsyncMock,
            return_value=_stub_user_settings({"agent_backend": "zai", "zai_api_key": USER_ZAI_KEY}),
        ):
            response = await async_client.get("/api/settings")

        data = response.json()
        _assert_no_secrets(response.text, data)
        assert data["zai_api_key_configured"] is True
        assert data["openai_api_key_configured"] is False
        assert data["agent_backend"] == "zai"

    async def test_default_backend_is_studyaio_provided(self, async_client, instance_credentials):
        """A user with no override is on the instance provider, not on `zai`."""
        with patch(
            "app.services.settings_service._get_or_create_user_settings",
            new_callable=AsyncMock,
            return_value=_stub_user_settings(),
        ):
            response = await async_client.get("/api/settings")

        assert response.json()["agent_backend"] == "studyaio"

"""SEC-01 (GL#11) and SEC-03 (GL#14): operator-only provider settings.

`claude_code_path` and `claude_model` are never user-settable: the first is the
executable the worker runs. Provider base URLs are operator-only unless the
deployment is self-hosted, where they are accepted only if they resolve to
public addresses. Stored legacy values are ignored on the read path.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import settings_service

USER_ID = "user-001"


def _row(stored: dict) -> MagicMock:
    row = MagicMock()
    row.settings_json = stored
    row.theme = "system"
    row.language = "en"
    row.content_language = False
    row.dashboard_layout = None
    row.updated_at = datetime.now(UTC)
    return row


@pytest.fixture
def session():
    s = AsyncMock()
    s.add = MagicMock()
    return s


def _self_hosted(value: bool):
    return patch.object(settings_service.settings, "self_hosted", value)


def _public_dns():
    return patch(
        "app.core.url_safety.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
    )


class TestOperatorOnlyKeys:
    @pytest.mark.parametrize("key", ["claude_code_path", "claude_model"])
    def test_keys_not_user_settable(self, key):
        assert key not in settings_service.ALLOWED_KEYS

    @pytest.mark.parametrize(
        ("key", "value"),
        [("claude_code_path", "/tmp/evil"), ("claude_model", "opus")],
    )
    def test_validate_rejects_with_operator_message(self, key, value):
        with pytest.raises(ValueError, match="operator"):
            settings_service.validate_setting(key, value)

    @pytest.mark.asyncio
    async def test_put_rejects_and_persists_nothing(self, session):
        row = _row({})
        with patch.object(
            settings_service, "_get_or_create_user_settings", AsyncMock(return_value=row)
        ):
            with pytest.raises(ValueError, match="operator"):
                await settings_service.update_user_settings(
                    session, USER_ID, {"claude_code_path": "/tmp/evil"}
                )
        assert row.settings_json == {}
        session.commit.assert_not_awaited()

    def test_stored_legacy_values_not_in_agent_config(self):
        cfg = settings_service._agent_config_from_overrides(
            {
                "agent_backend": "claude_code",
                "claude_cli_credentials": "{}",
                "claude_code_path": "/tmp/evil",
                "claude_model": "haiku",
            }
        )
        assert cfg is not None
        assert "claude_code_path" not in cfg
        assert "claude_model" not in cfg
        # the factory reads .get(key, ""): empty means "use the operator's env"
        assert cfg.get("claude_code_path", "") == ""

    def test_stored_legacy_values_not_in_public_view(self):
        view = settings_service._public_view(
            {"claude_code_path": "/tmp/evil", "claude_model": "haiku"}
        )
        assert view["claude_code_path"] == settings_service.settings.claude_code_path
        assert view["claude_model"] == settings_service.settings.claude_model


class TestBaseUrlsNotSelfHosted:
    @pytest.mark.parametrize("key", ["ollama_base_url", "zai_base_url"])
    @pytest.mark.asyncio
    async def test_put_rejected(self, session, key):
        row = _row({})
        with (
            _self_hosted(False),
            patch.object(
                settings_service, "_get_or_create_user_settings", AsyncMock(return_value=row)
            ),
            pytest.raises(ValueError, match="operator"),
        ):
            await settings_service.update_user_settings(session, USER_ID, {key: "https://x.com"})
        assert row.settings_json == {}

    def test_stored_urls_ignored_in_agent_config(self):
        stored = {
            "agent_backend": "ollama",
            "ollama_base_url": "http://169.254.169.254",
            "zai_base_url": "http://127.0.0.1:1",
        }
        with _self_hosted(False):
            cfg = settings_service._agent_config_from_overrides(stored)
        assert cfg is not None
        assert cfg["ollama_base_url"] == ""
        assert cfg["zai_base_url"] == ""

    def test_stored_urls_hidden_in_public_view(self):
        with _self_hosted(False):
            view = settings_service._public_view(
                {"ollama_base_url": "http://10.0.0.1", "zai_base_url": "http://10.0.0.1"}
            )
        assert view["ollama_base_url"] == ""
        assert view["zai_base_url"] == settings_service.settings.zai_base_url


class TestBaseUrlsSelfHosted:
    @pytest.mark.parametrize("key", ["ollama_base_url", "zai_base_url"])
    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1:11434",
            "http://169.254.169.254/",
            "http://[::1]:11434",
            "http://10.0.0.5",
            "http://2130706433",
            "http://0177.0.0.1",
            "file:///etc/passwd",
        ],
    )
    @pytest.mark.asyncio
    async def test_put_rejects_unsafe(self, session, key, url):
        row = _row({})
        with (
            _self_hosted(True),
            patch.object(
                settings_service, "_get_or_create_user_settings", AsyncMock(return_value=row)
            ),
            pytest.raises(ValueError),
        ):
            await settings_service.update_user_settings(session, USER_ID, {key: url})
        assert row.settings_json == {}
        session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_put_rejects_hostname_resolving_private(self, session):
        row = _row({})
        with (
            _self_hosted(True),
            patch(
                "app.core.url_safety.socket.getaddrinfo",
                return_value=[(2, 1, 6, "", ("10.9.9.9", 0))],
            ),
            patch.object(
                settings_service, "_get_or_create_user_settings", AsyncMock(return_value=row)
            ),
            pytest.raises(ValueError),
        ):
            await settings_service.update_user_settings(
                session, USER_ID, {"ollama_base_url": "https://rebind.example.com"}
            )
        assert row.settings_json == {}

    @pytest.mark.asyncio
    async def test_put_accepts_public_url(self, session):
        row = _row({})
        with (
            _self_hosted(True),
            _public_dns(),
            patch.object(
                settings_service, "_get_or_create_user_settings", AsyncMock(return_value=row)
            ),
            patch.object(settings_service, "get_user_settings", AsyncMock(return_value={})),
        ):
            await settings_service.update_user_settings(
                session, USER_ID, {"ollama_base_url": "https://ollama.example.com"}
            )
        assert row.settings_json == {"ollama_base_url": "https://ollama.example.com"}

    def test_stored_unsafe_url_dropped_at_use_time(self):
        """A value stored before the rule, or whose DNS has since changed."""
        stored = {"agent_backend": "ollama", "ollama_base_url": "http://127.0.0.1:11434"}
        with _self_hosted(True):
            cfg = settings_service._agent_config_from_overrides(stored)
        assert cfg is not None
        assert cfg["ollama_base_url"] == ""

    def test_stored_safe_url_kept(self):
        stored = {"agent_backend": "ollama", "ollama_base_url": "https://ollama.example.com"}
        with _self_hosted(True), _public_dns():
            cfg = settings_service._agent_config_from_overrides(stored)
        assert cfg is not None
        assert cfg["ollama_base_url"] == "https://ollama.example.com"

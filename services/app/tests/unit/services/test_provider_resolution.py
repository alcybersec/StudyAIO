"""Provider resolution: "StudyAIO provided" vs an explicitly chosen provider.

The instance credential backs exactly one selection — `studyaio`. Choosing any
other provider means the user's own credential is used, and a missing one is an
error rather than a silent fall back to the operator's key (issue #30).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from app.agents.factory import get_agent
from app.config import settings as app_settings
from app.core.exceptions import ProviderCredentialError
from app.services import settings_service

INSTANCE_ZAI_KEY = "<test-placeholder>-instance-zai-key"
USER_ZAI_KEY = "<test-placeholder>-user-zai-key"
USER_ID = "user-001"


@pytest.fixture
def instance_zai():
    """The deployment is configured with Z.ai as its provider."""
    with (
        patch.object(app_settings, "zai_api_key", SecretStr(INSTANCE_ZAI_KEY)),
        patch.object(app_settings, "agent_backend", "zai"),
    ):
        yield


def _session_with(overrides: dict | None):
    """AsyncSession stand-in whose user_settings row holds `overrides`."""
    session = AsyncMock()
    result = MagicMock()
    if overrides is None:
        result.scalar_one_or_none.return_value = None
    else:
        row = MagicMock()
        row.settings_json = overrides
        result.scalar_one_or_none.return_value = row
    session.execute = AsyncMock(return_value=result)
    return session


@pytest.mark.asyncio
class TestStudyAIOProvided:
    """`studyaio` resolves to the instance provider and its credential."""

    async def test_explicit_studyaio_yields_no_user_config(self, instance_zai):
        session = _session_with({"agent_backend": "studyaio"})
        assert await settings_service.get_user_agent_config(session, USER_ID) is None

    async def test_no_override_yields_no_user_config(self, instance_zai):
        session = _session_with({})
        assert await settings_service.get_user_agent_config(session, USER_ID) is None

    async def test_resolves_to_the_instance_adapter_and_key(self, instance_zai):
        from app.agents.zai_adapter import ZaiAdapter

        session = _session_with({"agent_backend": "studyaio"})
        config = await settings_service.get_user_agent_config(session, USER_ID)

        agent = get_agent(user_settings=config)
        assert isinstance(agent, ZaiAdapter)
        assert agent._api_key == INSTANCE_ZAI_KEY

    async def test_uses_instance_provider_is_true(self, instance_zai):
        session = _session_with({"agent_backend": "studyaio"})
        assert await settings_service.uses_instance_provider(session, USER_ID) is True

    async def test_uses_instance_provider_false_for_own_provider(self, instance_zai):
        session = _session_with({"agent_backend": "zai", "zai_api_key": USER_ZAI_KEY})
        assert await settings_service.uses_instance_provider(session, USER_ID) is False


@pytest.mark.asyncio
class TestExplicitProviderNeverInheritsInstanceCredential:
    """The root of #30: an explicit selection must not fall back."""

    async def test_config_carries_no_instance_credential(self, instance_zai):
        session = _session_with({"agent_backend": "zai"})
        config = await settings_service.get_user_agent_config(session, USER_ID)

        assert config is not None
        assert config["zai_api_key"] == ""
        assert INSTANCE_ZAI_KEY not in str(config)

    async def test_factory_refuses_a_credential_less_selection(self, instance_zai):
        session = _session_with({"agent_backend": "zai"})
        config = await settings_service.get_user_agent_config(session, USER_ID)

        with pytest.raises(ProviderCredentialError, match="zai"):
            get_agent(user_settings=config)

    @pytest.mark.parametrize(
        ("backend", "credential"),
        [
            ("anthropic_api", "anthropic_api_key"),
            ("openai", "openai_api_key"),
            ("claude_code", "claude_cli_credentials"),
            ("ollama", "ollama_base_url"),
        ],
    )
    async def test_every_provider_requires_its_own_credential(
        self, instance_zai, backend, credential
    ):
        session = _session_with({"agent_backend": backend})
        config = await settings_service.get_user_agent_config(session, USER_ID)

        assert config[credential] == ""
        with pytest.raises(ProviderCredentialError):
            get_agent(user_settings=config)

    async def test_own_key_is_used(self, instance_zai):
        from app.agents.zai_adapter import ZaiAdapter

        session = _session_with({"agent_backend": "zai", "zai_api_key": USER_ZAI_KEY})
        config = await settings_service.get_user_agent_config(session, USER_ID)

        agent = get_agent(user_settings=config)
        assert isinstance(agent, ZaiAdapter)
        assert agent._api_key == USER_ZAI_KEY


@pytest.mark.asyncio
class TestSecretUpdateSemantics:
    """PUT must round-trip: an empty secret means "leave it alone"."""

    def _stub(self, stored: dict):
        row = MagicMock()
        row.settings_json = dict(stored)
        row.theme = "system"
        row.dashboard_layout = None
        return row

    async def _update(self, stored: dict, updates: dict) -> dict:
        session = AsyncMock()
        session.commit = AsyncMock()
        row = self._stub(stored)
        with patch.object(
            settings_service,
            "_get_or_create_user_settings",
            new_callable=AsyncMock,
            return_value=row,
        ):
            await settings_service.update_user_settings(session, USER_ID, updates)
        return row.settings_json

    async def test_empty_secret_leaves_the_stored_value(self):
        stored = await self._update(
            {"agent_backend": "zai", "zai_api_key": USER_ZAI_KEY}, {"zai_api_key": ""}
        )
        assert stored["zai_api_key"] == USER_ZAI_KEY

    async def test_whitespace_secret_leaves_the_stored_value(self):
        stored = await self._update(
            {"agent_backend": "zai", "zai_api_key": USER_ZAI_KEY}, {"zai_api_key": "   "}
        )
        assert stored["zai_api_key"] == USER_ZAI_KEY

    async def test_non_empty_secret_replaces(self):
        stored = await self._update(
            {"agent_backend": "zai", "zai_api_key": USER_ZAI_KEY},
            {"zai_api_key": "<test-placeholder>-replacement"},
        )
        assert stored["zai_api_key"] == "<test-placeholder>-replacement"

    async def test_non_secret_empty_value_is_not_swallowed(self):
        """Only credentials get the "empty means unchanged" treatment."""
        with pytest.raises(ValueError, match="ollama_model"):
            await self._update({"ollama_model": "llama3.2"}, {"ollama_model": ""})

    async def test_clear_secrets_removes_a_stored_credential(self):
        stored = await self._update(
            {"agent_backend": "zai", "zai_api_key": USER_ZAI_KEY},
            {"clear_secrets": ["zai_api_key"]},
        )
        assert "zai_api_key" not in stored

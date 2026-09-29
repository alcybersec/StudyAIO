"""Tests for agent factory with per-user settings.

A `user_settings` dict means the user chose a provider of their own, so the
factory must find their credential in it. Reaching for the instance credential
instead was issue #30, and these tests pin the refusal.
"""

import json
from unittest.mock import patch

import pytest

from app.agents.factory import get_agent
from app.core.exceptions import ProviderCredentialError


class TestGetAgentWithUserSettings:
    """Tests for get_agent(user_settings=...) per-user credential flow."""

    def test_no_user_settings_uses_system_default(self):
        """When user_settings is None, falls back to system default."""
        with patch("app.agents.factory.get_effective_setting", return_value="claude_code"):
            from app.agents.claude_code import ClaudeCodeAdapter

            agent = get_agent(user_settings=None)
            assert isinstance(agent, ClaudeCodeAdapter)
            assert agent._credentials_json is None

    def test_user_settings_anthropic_api_key(self):
        """User's own Anthropic API key is passed to adapter."""
        user_settings = {
            "agent_backend": "anthropic_api",
            "anthropic_api_key": "sk-ant-user-key-123",
            "claude_model": "haiku",
        }
        with patch("app.agents.anthropic_api.get_effective_setting", return_value="test"):
            from app.agents.anthropic_api import AnthropicAPIAdapter

            agent = get_agent(user_settings=user_settings)
            assert isinstance(agent, AnthropicAPIAdapter)
            assert agent._api_key == "sk-ant-user-key-123"

    def test_user_settings_openai_key(self):
        """User's own OpenAI key is passed to adapter."""
        user_settings = {
            "agent_backend": "openai",
            "openai_api_key": "sk-user-openai-key",
            "openai_model": "gpt-4o-mini",
        }
        with patch("app.agents.openai_adapter.get_effective_setting", return_value="test"):
            from app.agents.openai_adapter import OpenAIAdapter

            agent = get_agent(user_settings=user_settings)
            assert isinstance(agent, OpenAIAdapter)
            assert agent._api_key == "sk-user-openai-key"
            assert agent._model == "gpt-4o-mini"

    def test_user_settings_ollama(self):
        """User's Ollama config is passed to adapter."""
        user_settings = {
            "agent_backend": "ollama",
            "ollama_base_url": "http://myollama:11434",
            "ollama_model": "mistral",
        }
        with patch("app.agents.ollama_adapter.get_effective_setting", return_value="test"):
            from app.agents.ollama_adapter import OllamaAdapter

            agent = get_agent(user_settings=user_settings)
            assert isinstance(agent, OllamaAdapter)
            assert agent._base_url == "http://myollama:11434"
            assert agent._model == "mistral"

    def test_user_settings_claude_code_with_credentials(self):
        """User's CLI credentials are parsed and passed to adapter."""
        creds = {
            "claudeAiOauth": {
                "accessToken": "user-access-token",
                "refreshToken": "user-refresh-token",
            }
        }
        user_settings = {
            "agent_backend": "claude_code",
            "claude_code_path": "/usr/bin/claude",
            "claude_model": "sonnet",
            "claude_cli_credentials": json.dumps(creds),
        }
        with patch("app.agents.claude_code.get_effective_setting", return_value="test"):
            from app.agents.claude_code import ClaudeCodeAdapter

            agent = get_agent(user_settings=user_settings)
            assert isinstance(agent, ClaudeCodeAdapter)
            assert agent._credentials_json == creds
            assert agent._model == "sonnet"

    def test_user_settings_claude_code_empty_credentials_is_refused(self):
        """Empty credentials would fall through to the host's own `claude login`."""
        user_settings = {
            "agent_backend": "claude_code",
            "claude_code_path": "",
            "claude_model": "",
            "claude_cli_credentials": "",
        }
        with pytest.raises(ProviderCredentialError, match="claude_code"):
            get_agent(user_settings=user_settings)

    def test_user_settings_invalid_credentials_json_is_refused(self):
        """Unparseable credentials must not silently become "no credentials"."""
        user_settings = {
            "agent_backend": "claude_code",
            "claude_code_path": "",
            "claude_model": "",
            "claude_cli_credentials": "not valid json {{{",
        }
        with pytest.raises(ProviderCredentialError, match="claude_cli_credentials"):
            get_agent(user_settings=user_settings)

    def test_no_backend_means_studyaio_provided(self):
        """An unset backend is "StudyAIO provided" — the instance's own account.

        The user's stored key is deliberately *not* used: they did not choose
        that provider, and the instance is what runs the call.
        """
        user_settings = {
            "agent_backend": "",
            "anthropic_api_key": "sk-ant-user",
        }
        with (
            patch("app.agents.factory.get_effective_setting", return_value="anthropic_api"),
            patch("app.agents.anthropic_api.get_effective_setting", return_value="instance-key"),
        ):
            from app.agents.anthropic_api import AnthropicAPIAdapter

            agent = get_agent(user_settings=user_settings)
            assert isinstance(agent, AnthropicAPIAdapter)
            assert agent._api_key == "instance-key"


class TestOutputLanguage:
    """`output_language` is a parameter of its own, not a key in user_settings.

    `get_user_agent_config()` returns None for every user on instance
    credentials (issue #30). A language riding inside that dict would have
    reached only the minority running their own API keys — the opposite of an
    app-wide setting.
    """

    def test_applied_on_the_instance_credential_path(self):
        """user_settings=None is what most accounts pass."""
        with patch("app.agents.factory.get_effective_setting", return_value="claude_code"):
            agent = get_agent(user_settings=None, output_language="ru")

        assert agent.output_language == "ru"
        assert "Russian" in agent.language_directive()

    def test_applied_on_the_own_provider_path(self):
        agent = get_agent(
            user_settings={
                "agent_backend": "openai",
                "openai_api_key": "sk-test",
                "openai_model": "gpt-4o",
            },
            output_language="ru",
        )

        assert agent.output_language == "ru"

    def test_absent_by_default(self):
        """Omitting it leaves every existing caller behaving exactly as before."""
        with patch("app.agents.factory.get_effective_setting", return_value="claude_code"):
            agent = get_agent()

        assert agent.output_language is None
        assert agent.language_directive() == ""

    def test_unsupported_tag_does_not_reach_the_prompt(self):
        with patch("app.agents.factory.get_effective_setting", return_value="claude_code"):
            agent = get_agent(user_settings=None, output_language="xx")

        assert agent.output_language is None

"""Tests for agent factory with per-user settings."""

import json

from unittest.mock import patch

from app.agents.factory import get_agent


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

    def test_user_settings_claude_code_empty_credentials(self):
        """Empty credentials string results in None credentials."""
        user_settings = {
            "agent_backend": "claude_code",
            "claude_code_path": "",
            "claude_model": "",
            "claude_cli_credentials": "",
        }
        with patch("app.agents.claude_code.get_effective_setting", return_value="test"):
            from app.agents.claude_code import ClaudeCodeAdapter

            agent = get_agent(user_settings=user_settings)
            assert isinstance(agent, ClaudeCodeAdapter)
            assert agent._credentials_json is None

    def test_user_settings_invalid_credentials_json(self):
        """Invalid JSON credentials result in None credentials."""
        user_settings = {
            "agent_backend": "claude_code",
            "claude_code_path": "",
            "claude_model": "",
            "claude_cli_credentials": "not valid json {{{",
        }
        with patch("app.agents.claude_code.get_effective_setting", return_value="test"):
            from app.agents.claude_code import ClaudeCodeAdapter

            agent = get_agent(user_settings=user_settings)
            assert isinstance(agent, ClaudeCodeAdapter)
            assert agent._credentials_json is None

    def test_user_settings_backend_falls_back_to_system(self):
        """When user_settings has no agent_backend, system default is used."""
        user_settings = {
            "agent_backend": "",
            "anthropic_api_key": "sk-ant-user",
        }
        with (
            patch("app.agents.factory.get_effective_setting", return_value="anthropic_api"),
            patch("app.agents.anthropic_api.get_effective_setting", return_value="test"),
        ):
            from app.agents.anthropic_api import AnthropicAPIAdapter

            agent = get_agent(user_settings=user_settings)
            assert isinstance(agent, AnthropicAPIAdapter)
            assert agent._api_key == "sk-ant-user"

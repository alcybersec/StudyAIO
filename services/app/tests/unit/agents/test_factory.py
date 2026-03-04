"""Tests for agent factory."""

from unittest.mock import patch

from app.agents.factory import get_agent


class TestGetAgent:
    """Tests for get_agent() factory function."""

    def test_default_returns_claude_code(self):
        """Default backend returns ClaudeCodeAdapter."""
        with patch("app.agents.factory.get_effective_setting", return_value="claude_code"):
            from app.agents.claude_code import ClaudeCodeAdapter

            agent = get_agent()
            assert isinstance(agent, ClaudeCodeAdapter)

    def test_anthropic_api_returns_anthropic_adapter(self):
        """anthropic_api backend returns AnthropicAPIAdapter."""
        with (
            patch("app.agents.factory.get_effective_setting", return_value="anthropic_api"),
            patch("app.agents.anthropic_api.get_effective_setting", return_value="test"),
        ):
            from app.agents.anthropic_api import AnthropicAPIAdapter

            agent = get_agent()
            assert isinstance(agent, AnthropicAPIAdapter)

    def test_openai_returns_openai_adapter(self):
        """openai backend returns OpenAIAdapter."""
        with (
            patch("app.agents.factory.get_effective_setting", return_value="openai"),
            patch("app.agents.openai_adapter.get_effective_setting", return_value="test"),
        ):
            from app.agents.openai_adapter import OpenAIAdapter

            agent = get_agent()
            assert isinstance(agent, OpenAIAdapter)

    def test_ollama_returns_ollama_adapter(self):
        """ollama backend returns OllamaAdapter."""
        with (
            patch("app.agents.factory.get_effective_setting", return_value="ollama"),
            patch("app.agents.ollama_adapter.get_effective_setting", return_value="test"),
        ):
            from app.agents.ollama_adapter import OllamaAdapter

            agent = get_agent()
            assert isinstance(agent, OllamaAdapter)

    def test_unknown_backend_falls_back_to_claude_code(self):
        """Unknown backend falls back to ClaudeCodeAdapter."""
        with patch("app.agents.factory.get_effective_setting", return_value="unknown_backend"):
            from app.agents.claude_code import ClaudeCodeAdapter

            agent = get_agent()
            assert isinstance(agent, ClaudeCodeAdapter)

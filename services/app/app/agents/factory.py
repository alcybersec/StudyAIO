"""Agent factory — returns the configured agent adapter."""

from typing import Any

from app.agents.base import AgentAdapter
from app.services.settings_service import get_effective_setting


def get_agent(user_settings: dict[str, Any] | None = None) -> AgentAdapter:
    """Get the configured agent adapter instance.

    When user_settings is provided, uses per-user backend selection and
    credentials. Falls back to system defaults when no user settings.

    Args:
        user_settings: Optional per-user AI config from get_user_agent_config().
            Keys: agent_backend, claude_code_path, claude_model,
            anthropic_api_key, openai_api_key, openai_model,
            ollama_base_url, ollama_model, claude_cli_credentials.

    Returns:
        An AgentAdapter implementation.
    """
    if user_settings:
        backend = user_settings.get("agent_backend") or get_effective_setting("agent_backend")
    else:
        backend = get_effective_setting("agent_backend")

    if backend == "anthropic_api":
        from app.agents.anthropic_api import AnthropicAPIAdapter

        if user_settings and user_settings.get("anthropic_api_key"):
            return AnthropicAPIAdapter(
                api_key=user_settings["anthropic_api_key"],
                model=user_settings.get("claude_model", ""),
            )
        return AnthropicAPIAdapter()

    if backend == "openai":
        from app.agents.openai_adapter import OpenAIAdapter

        if user_settings and user_settings.get("openai_api_key"):
            return OpenAIAdapter(
                api_key=user_settings["openai_api_key"],
                model=user_settings.get("openai_model", ""),
            )
        return OpenAIAdapter()

    if backend == "ollama":
        from app.agents.ollama_adapter import OllamaAdapter

        if user_settings:
            return OllamaAdapter(
                base_url=user_settings.get("ollama_base_url", ""),
                model=user_settings.get("ollama_model", ""),
            )
        return OllamaAdapter()

    # Default: claude_code
    from app.agents.claude_code import ClaudeCodeAdapter

    if user_settings:
        credentials_json = None
        creds_str = user_settings.get("claude_cli_credentials", "")
        if creds_str:
            import json

            try:
                credentials_json = json.loads(creds_str)
            except (json.JSONDecodeError, TypeError):
                pass

        return ClaudeCodeAdapter(
            cli_path=user_settings.get("claude_code_path", ""),
            model=user_settings.get("claude_model", ""),
            credentials_json=credentials_json,
        )
    return ClaudeCodeAdapter()

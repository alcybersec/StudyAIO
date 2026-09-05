"""Agent factory — returns the configured agent adapter.

This is the single choke point every AI call passes through, so it is where
the instance-vs-own-provider boundary is enforced: `user_settings` describes a
provider the *user* chose, and a chosen provider with no credential of its own
is refused. Falling through to the instance credential is what let any account
spend the operator's key (issue #30).
"""

from typing import Any

from app.agents.base import AgentAdapter
from app.core.exceptions import ProviderCredentialError
from app.services.settings_service import (
    BACKEND_REQUIRED_KEY,
    STUDYAIO_BACKEND,
    get_effective_setting,
)


def get_agent(user_settings: dict[str, Any] | None = None) -> AgentAdapter:
    """Get the configured agent adapter instance.

    Args:
        user_settings: Per-user AI config from get_user_agent_config(), or
            None for "StudyAIO provided" — the instance backend and its
            environment-configured credentials.
            Keys: agent_backend, claude_code_path, claude_model,
            anthropic_api_key, openai_api_key, openai_model,
            zai_api_key, zai_model, zai_base_url,
            ollama_base_url, ollama_model, claude_cli_credentials.

    Returns:
        An AgentAdapter implementation.

    Raises:
        ProviderCredentialError: If the user selected a provider explicitly but
            stored no credential for it.
    """
    if user_settings:
        backend = user_settings.get("agent_backend") or STUDYAIO_BACKEND
        if backend == STUDYAIO_BACKEND:
            user_settings = None
        else:
            required = BACKEND_REQUIRED_KEY.get(backend)
            if required and not str(user_settings.get(required) or "").strip():
                raise ProviderCredentialError(backend, required)

    if not user_settings:
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

    if backend == "zai":
        from app.agents.zai_adapter import ZaiAdapter

        if user_settings and user_settings.get("zai_api_key"):
            return ZaiAdapter(
                api_key=user_settings["zai_api_key"],
                model=user_settings.get("zai_model", ""),
                base_url=user_settings.get("zai_base_url", ""),
            )
        return ZaiAdapter()

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
        # Unparseable credentials would otherwise yield credentials_json=None,
        # which makes the adapter use the host's own `claude login` — the
        # operator's Max subscription. Refuse instead.
        import json

        try:
            credentials_json = json.loads(user_settings.get("claude_cli_credentials", ""))
        except (json.JSONDecodeError, TypeError) as e:
            raise ProviderCredentialError("claude_code", "claude_cli_credentials") from e

        return ClaudeCodeAdapter(
            cli_path=user_settings.get("claude_code_path", ""),
            model=user_settings.get("claude_model", ""),
            credentials_json=credentials_json,
        )
    return ClaudeCodeAdapter()

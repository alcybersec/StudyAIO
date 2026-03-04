"""Agent factory — returns the configured agent adapter."""

from app.agents.base import AgentAdapter
from app.services.settings_service import get_effective_setting


def get_agent() -> AgentAdapter:
    """Get the configured agent adapter instance.

    Reads agent_backend from settings to select the adapter:
    - "claude_code": ClaudeCodeAdapter (CLI subprocess)
    - "anthropic_api": AnthropicAPIAdapter (SDK direct)
    - "openai": OpenAIAdapter (OpenAI SDK)
    - "ollama": OllamaAdapter (local Ollama server)

    Returns:
        An AgentAdapter implementation.
    """
    backend = get_effective_setting("agent_backend")

    if backend == "anthropic_api":
        from app.agents.anthropic_api import AnthropicAPIAdapter

        return AnthropicAPIAdapter()

    if backend == "openai":
        from app.agents.openai_adapter import OpenAIAdapter

        return OpenAIAdapter()

    if backend == "ollama":
        from app.agents.ollama_adapter import OllamaAdapter

        return OllamaAdapter()

    # Default: claude_code
    from app.agents.claude_code import ClaudeCodeAdapter

    return ClaudeCodeAdapter()

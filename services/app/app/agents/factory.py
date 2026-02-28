"""Agent factory — returns the configured agent adapter."""

from app.agents.base import AgentAdapter
from app.agents.claude_code import ClaudeCodeAdapter


def get_agent() -> AgentAdapter:
    """Get the configured agent adapter instance.

    Currently always returns ClaudeCodeAdapter. Future versions may
    select based on config (e.g., AnthropicAPIAdapter, OllamaAdapter).

    Returns:
        An AgentAdapter implementation.
    """
    return ClaudeCodeAdapter()

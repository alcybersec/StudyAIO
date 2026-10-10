"""Env-only AI settings shared by the agent adapters and the settings service.

Session-free by design: this module reads ``app.config.settings`` and nothing
else, so ``app.agents`` can use it without importing the services layer
(ADR 0002, R-002a). ``app.services.settings_service`` re-exports every name.
"""

from typing import Any

from app.config import settings

#: "StudyAIO provided" — use the instance's configured backend and credentials.
STUDYAIO_BACKEND = "studyaio"

#: What a user must supply for each provider they select explicitly. Absent it,
#: the agent factory refuses rather than reaching for the instance credential.
#: Ollama has no API key, so its endpoint plays the part: pointing at the
#: instance's own Ollama would be spending the operator's hardware under a
#: selection that claims to be the user's own.
BACKEND_REQUIRED_KEY = {
    "claude_code": "claude_cli_credentials",
    "anthropic_api": "anthropic_api_key",
    "openai": "openai_api_key",
    "zai": "zai_api_key",
    "ollama": "ollama_base_url",
}


def _defaults() -> dict[str, Any]:
    """Return default values from env-based config."""
    return {
        "claude_code_path": settings.claude_code_path,
        "claude_model": settings.claude_model,
        "agent_backend": settings.agent_backend,
        "anthropic_api_key": settings.anthropic_api_key.get_secret_value(),
        "openai_api_key": settings.openai_api_key.get_secret_value(),
        "openai_model": settings.openai_model,
        "zai_api_key": settings.zai_api_key.get_secret_value(),
        "zai_model": settings.zai_model,
        "zai_base_url": settings.zai_base_url,
        "ollama_base_url": settings.ollama_base_url,
        "ollama_model": settings.ollama_model,
        "classification_confidence_threshold": settings.classification_confidence_threshold,
        "flashcard_count_per_week": settings.flashcard_count_per_week,
        "quiz_question_count_per_week": settings.quiz_question_count_per_week,
        "chunk_size_tokens": settings.chunk_size_tokens,
        "chunk_overlap_tokens": settings.chunk_overlap_tokens,
        "max_upload_size_mb": settings.max_upload_size_mb,
    }


def get_effective_setting(key: str) -> Any:
    """Get the effective value of a setting using env defaults only.

    This is the sync fallback used by pipeline tasks that don't have
    a DB session or user_id readily available. Returns env defaults.

    Args:
        key: Setting key name.

    Returns:
        The default value from environment config.
    """
    defaults = _defaults()
    return defaults.get(key, getattr(settings, key, None))

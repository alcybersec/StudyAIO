"""Settings service — DB-backed per-user configuration with env defaults.

Settings are stored per-user in the `user_settings` table (JSONB).
When a user has no stored setting for a key, the environment-based
default from `app.config.settings` is used.

For pipeline tasks (synchronous context without a DB session),
`get_effective_setting()` falls back to env defaults only.
"""

from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.utils import generate_id
from app.models.user_settings import UserSettings

logger = structlog.get_logger()

# Keys that can be modified via the settings API
ALLOWED_KEYS = {
    "claude_code_path",
    "claude_model",
    "agent_backend",
    "anthropic_api_key",
    "openai_api_key",
    "openai_model",
    "ollama_base_url",
    "ollama_model",
    "embedding_backend",
    "classification_confidence_threshold",
    "flashcard_count_per_week",
    "quiz_question_count_per_week",
    "chunk_size_tokens",
    "chunk_overlap_tokens",
    "max_upload_size_mb",
}

VALID_MODELS = {"opus", "sonnet", "haiku"}
VALID_BACKENDS = {"claude_code", "anthropic_api", "openai", "ollama"}
VALID_EMBEDDING_BACKENDS = {"sentence_transformers", "openai", "ollama"}

# Validation rules: (type, min, max)
_VALIDATORS: dict[str, tuple[type, Any, Any]] = {
    "claude_code_path": (str, None, None),
    "claude_model": (str, None, None),
    "agent_backend": (str, None, None),
    "anthropic_api_key": (str, None, None),
    "openai_api_key": (str, None, None),
    "openai_model": (str, None, None),
    "ollama_base_url": (str, None, None),
    "ollama_model": (str, None, None),
    "embedding_backend": (str, None, None),
    "classification_confidence_threshold": (float, 0.0, 1.0),
    "flashcard_count_per_week": (int, 1, 100),
    "quiz_question_count_per_week": (int, 1, 100),
    "chunk_size_tokens": (int, 50, 5000),
    "chunk_overlap_tokens": (int, 0, 500),
    "max_upload_size_mb": (int, 1, 1000),
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
        "ollama_base_url": settings.ollama_base_url,
        "ollama_model": settings.ollama_model,
        "embedding_backend": settings.embedding_backend,
        "classification_confidence_threshold": settings.classification_confidence_threshold,
        "flashcard_count_per_week": settings.flashcard_count_per_week,
        "quiz_question_count_per_week": settings.quiz_question_count_per_week,
        "chunk_size_tokens": settings.chunk_size_tokens,
        "chunk_overlap_tokens": settings.chunk_overlap_tokens,
        "max_upload_size_mb": settings.max_upload_size_mb,
    }


def validate_setting(key: str, value: Any) -> Any:
    """Validate a single setting key/value.

    Args:
        key: Setting key name.
        value: Proposed value.

    Returns:
        Coerced value.

    Raises:
        ValueError: If key is unknown or value is invalid.
    """
    if key not in ALLOWED_KEYS:
        raise ValueError(f"Unknown setting: {key}")

    expected_type, min_val, max_val = _VALIDATORS[key]

    if key == "claude_model":
        if value not in VALID_MODELS:
            raise ValueError(f"claude_model must be one of {sorted(VALID_MODELS)}, got '{value}'")
        return value

    if key == "agent_backend":
        if value not in VALID_BACKENDS:
            raise ValueError(
                f"agent_backend must be one of {sorted(VALID_BACKENDS)}, got '{value}'"
            )
        return value

    if key == "anthropic_api_key":
        if not isinstance(value, str):
            raise ValueError("anthropic_api_key must be a string")
        return value.strip()

    if key == "openai_api_key":
        if not isinstance(value, str):
            raise ValueError("openai_api_key must be a string")
        return value.strip()

    if key == "openai_model":
        if not isinstance(value, str) or not value.strip():
            raise ValueError("openai_model must be a non-empty string")
        return value.strip()

    if key == "ollama_base_url":
        if not isinstance(value, str) or not value.strip():
            raise ValueError("ollama_base_url must be a non-empty string")
        return value.strip()

    if key == "ollama_model":
        if not isinstance(value, str) or not value.strip():
            raise ValueError("ollama_model must be a non-empty string")
        return value.strip()

    if key == "embedding_backend":
        if value not in VALID_EMBEDDING_BACKENDS:
            raise ValueError(
                f"embedding_backend must be one of {sorted(VALID_EMBEDDING_BACKENDS)}, got '{value}'"
            )
        return value

    if key == "claude_code_path":
        if not isinstance(value, str) or not value.strip():
            raise ValueError("claude_code_path must be a non-empty string")
        return value.strip()

    # Numeric types
    if expected_type is float:
        try:
            value = float(value)
        except (TypeError, ValueError) as e:
            raise ValueError(f"{key} must be a number") from e
        if min_val is not None and value < min_val:
            raise ValueError(f"{key} must be >= {min_val}")
        if max_val is not None and value > max_val:
            raise ValueError(f"{key} must be <= {max_val}")
        return value

    if expected_type is int:
        if isinstance(value, float) and not value.is_integer():
            raise ValueError(f"{key} must be an integer")
        try:
            value = int(value)
        except (TypeError, ValueError) as e:
            raise ValueError(f"{key} must be an integer") from e
        if min_val is not None and value < min_val:
            raise ValueError(f"{key} must be >= {min_val}")
        if max_val is not None and value > max_val:
            raise ValueError(f"{key} must be <= {max_val}")
        return value

    return value


async def _get_or_create_user_settings(session: AsyncSession, user_id: str) -> UserSettings:
    """Get existing UserSettings or create with defaults.

    Args:
        session: Database session.
        user_id: User UUID.

    Returns:
        UserSettings instance.
    """
    result = await session.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    user_settings = result.scalar_one_or_none()
    if user_settings:
        return user_settings

    user_settings = UserSettings(
        id=generate_id(),
        user_id=user_id,
        settings_json={},
        theme="system",
    )
    session.add(user_settings)
    await session.flush()
    logger.info("user_settings_created", user_id=user_id)
    return user_settings


async def get_user_settings(session: AsyncSession, user_id: str) -> dict[str, Any]:
    """Get merged settings for a user (env defaults + per-user overrides).

    Args:
        session: Database session.
        user_id: User UUID.

    Returns:
        Dict of all settings with effective values.
    """
    merged = _defaults()
    user_settings = await _get_or_create_user_settings(session, user_id)
    overrides = user_settings.settings_json or {}
    for key in ALLOWED_KEYS:
        if key in overrides:
            merged[key] = overrides[key]
    # Include theme and dashboard_layout
    merged["theme"] = user_settings.theme
    merged["dashboard_layout"] = user_settings.dashboard_layout
    return merged


async def update_user_settings(
    session: AsyncSession, user_id: str, updates: dict[str, Any]
) -> dict[str, Any]:
    """Validate and persist per-user setting updates.

    Args:
        session: Database session.
        user_id: User UUID.
        updates: Dict of key/value pairs to update.

    Returns:
        Full merged settings after update.

    Raises:
        ValueError: If any key or value is invalid.
    """
    # Handle special non-settings-json keys
    theme = updates.pop("theme", None)
    dashboard_layout = updates.pop("dashboard_layout", None)

    # Validate remaining settings
    validated: dict[str, Any] = {}
    for key, value in updates.items():
        validated[key] = validate_setting(key, value)

    user_settings = await _get_or_create_user_settings(session, user_id)

    # Update settings_json
    if validated:
        current = dict(user_settings.settings_json or {})
        current.update(validated)
        user_settings.settings_json = current

    # Update theme
    if theme is not None:
        if theme not in ("light", "dark", "system"):
            raise ValueError("theme must be one of: light, dark, system")
        user_settings.theme = theme

    # Update dashboard layout
    if dashboard_layout is not None:
        user_settings.dashboard_layout = dashboard_layout

    user_settings.updated_at = datetime.utcnow()
    await session.commit()
    logger.info("user_settings_updated", user_id=user_id, keys=list(updates.keys()))

    return await get_user_settings(session, user_id)


async def get_effective_setting_async(
    session: AsyncSession, user_id: str, key: str
) -> Any:
    """Get the effective value of a single setting for a user.

    Args:
        session: Database session.
        user_id: User UUID.
        key: Setting key name.

    Returns:
        The effective value (user override > env default).
    """
    all_settings = await get_user_settings(session, user_id)
    return all_settings.get(key, getattr(settings, key, None))


# ── Sync fallback for pipeline consumers ──────────────────────────────

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


# ── Backward compatibility ────────────────────────────────────────────
# These sync functions are kept for existing code that hasn't been
# migrated to async per-user settings yet.

def get_all_settings() -> dict[str, Any]:
    """Get merged settings using env defaults only (sync, no user context).

    Returns:
        Dict of all configurable settings with default values.
    """
    return _defaults()


def update_settings(updates: dict[str, Any]) -> dict[str, Any]:
    """Validate settings (sync, no persistence — backward compat).

    Args:
        updates: Dict of key/value pairs to validate.

    Returns:
        Full defaults (updates are validated but not persisted in sync mode).

    Raises:
        ValueError: If any key or value is invalid.
    """
    for key, value in updates.items():
        validate_setting(key, value)
    # In sync mode without DB, just return defaults
    # The API layer should use the async version
    return _defaults()

"""Settings service — JSON file-backed runtime configuration."""

import json
from pathlib import Path
from typing import Any

import structlog

from app.config import settings

logger = structlog.get_logger()

# Keys that can be modified via the settings API
ALLOWED_KEYS = {
    "claude_code_path",
    "claude_model",
    "classification_confidence_threshold",
    "flashcard_count_per_week",
    "quiz_question_count_per_week",
    "chunk_size_tokens",
    "chunk_overlap_tokens",
}

VALID_MODELS = {"opus", "sonnet", "haiku"}

# Validation rules: (type, min, max)
_VALIDATORS: dict[str, tuple[type, Any, Any]] = {
    "claude_code_path": (str, None, None),
    "claude_model": (str, None, None),
    "classification_confidence_threshold": (float, 0.0, 1.0),
    "flashcard_count_per_week": (int, 1, 100),
    "quiz_question_count_per_week": (int, 1, 100),
    "chunk_size_tokens": (int, 50, 5000),
    "chunk_overlap_tokens": (int, 0, 500),
}


def _settings_path() -> Path:
    """Return path to the settings JSON file."""
    return Path(settings.data_dir) / "settings.json"


def _read_overrides() -> dict[str, Any]:
    """Read saved overrides from JSON file."""
    path = _settings_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("settings_read_failed", error=str(e))
        return {}


def _defaults() -> dict[str, Any]:
    """Return default values from env-based config."""
    return {
        "claude_code_path": settings.claude_code_path,
        "claude_model": settings.claude_model,
        "classification_confidence_threshold": settings.classification_confidence_threshold,
        "flashcard_count_per_week": settings.flashcard_count_per_week,
        "quiz_question_count_per_week": settings.quiz_question_count_per_week,
        "chunk_size_tokens": settings.chunk_size_tokens,
        "chunk_overlap_tokens": settings.chunk_overlap_tokens,
    }


def get_all_settings() -> dict[str, Any]:
    """Get merged settings (defaults + JSON overrides).

    Returns:
        Dict of all configurable settings with effective values.
    """
    merged = _defaults()
    overrides = _read_overrides()
    for key in ALLOWED_KEYS:
        if key in overrides:
            merged[key] = overrides[key]
    return merged


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


def update_settings(updates: dict[str, Any]) -> dict[str, Any]:
    """Validate and persist setting updates.

    Args:
        updates: Dict of key/value pairs to update.

    Returns:
        Full merged settings after update.

    Raises:
        ValueError: If any key or value is invalid.
    """
    # Validate all updates first
    validated: dict[str, Any] = {}
    for key, value in updates.items():
        validated[key] = validate_setting(key, value)

    # Merge with existing overrides
    overrides = _read_overrides()
    overrides.update(validated)

    # Write to disk
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(overrides, indent=2))
    logger.info("settings_updated", keys=list(validated.keys()))

    return get_all_settings()


def get_effective_setting(key: str) -> Any:
    """Get the effective value of a single setting.

    Args:
        key: Setting key name.

    Returns:
        The effective value (override if set, else default).
    """
    all_settings = get_all_settings()
    return all_settings.get(key, getattr(settings, key, None))

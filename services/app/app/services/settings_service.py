"""Settings service — DB-backed per-user configuration with env defaults.

Settings are stored per-user in the `user_settings` table (JSONB).
When a user has no stored setting for a key, the environment-based
default from `app.config.settings` is used.

For pipeline tasks (synchronous context without a DB session),
`get_effective_setting()` falls back to env defaults only.

Provider selection has two shapes, and the difference is a security boundary:

* ``studyaio`` — "StudyAIO provided". The instance's own backend and
  credentials, configured through the environment/secret store and never
  readable through this API. This is the default for every account.
* any other backend — the user's own provider. Their credential is the only
  one used; the instance credential is never inherited. That inheritance was
  the root of issue #30, where every authenticated account could read (and
  spend) the operator's key.

Credentials are therefore write-only: `get_user_settings` returns
``<key>_configured`` booleans, never values.
"""

import json
from datetime import UTC, datetime
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
    "zai_api_key",
    "zai_model",
    "zai_base_url",
    "ollama_base_url",
    "ollama_model",
    "claude_cli_credentials",
    "classification_confidence_threshold",
    "flashcard_count_per_week",
    "quiz_question_count_per_week",
    "chunk_size_tokens",
    "chunk_overlap_tokens",
    "max_upload_size_mb",
}

VALID_MODELS = {"opus", "sonnet", "haiku"}

#: "StudyAIO provided" — use the instance's configured backend and credentials.
STUDYAIO_BACKEND = "studyaio"

VALID_BACKENDS = {STUDYAIO_BACKEND, "claude_code", "anthropic_api", "openai", "zai", "ollama"}

#: Deliberately absent from ALLOWED_KEYS: `embedding_backend`. It is instance-wide
#: (`EMBEDDING_BACKEND`), read by `agents.embeddings.get_embedding_provider`, and
#: must not come back here as a per-user choice — issue #32. All of a deployment's
#: vectors share one `vector(384)` column and are only comparable when one model
#: produced them, so a per-user encoder needs a provenance column, a model-scoped
#: filter on every similarity query, and a re-index pipeline before the selection
#: means anything. Until that exists, offering the choice promises what it cannot
#: honour: the old dropdown let a user pick OpenAI, which was then called and
#: billed for vectors pgvector refused to store.

#: Never returned by the API. Written only, and only by the owning user.
SECRET_KEYS = frozenset(
    {
        "anthropic_api_key",
        "openai_api_key",
        "zai_api_key",
        "claude_cli_credentials",
    }
)

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

#: Resolved from the user's own settings only — never from instance defaults.
USER_ONLY_KEYS = frozenset(SECRET_KEYS | {"ollama_base_url"})

# Validation rules: (type, min, max)
_VALIDATORS: dict[str, tuple[type, Any, Any]] = {
    "claude_code_path": (str, None, None),
    "claude_model": (str, None, None),
    "agent_backend": (str, None, None),
    "anthropic_api_key": (str, None, None),
    "claude_cli_credentials": (str, None, None),
    "openai_api_key": (str, None, None),
    "openai_model": (str, None, None),
    "zai_api_key": (str, None, None),
    "zai_model": (str, None, None),
    "zai_base_url": (str, None, None),
    "ollama_base_url": (str, None, None),
    "ollama_model": (str, None, None),
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

    if key == "claude_cli_credentials":
        if not isinstance(value, str):
            raise ValueError("claude_cli_credentials must be a JSON string")
        value = value.strip()
        if not value:
            return ""  # Allow clearing
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as e:
            raise ValueError(f"claude_cli_credentials must be valid JSON: {e}") from e
        if not isinstance(parsed, dict):
            raise ValueError("claude_cli_credentials must be a JSON object")
        oauth = parsed.get("claudeAiOauth", {})
        if not oauth.get("accessToken") or not oauth.get("refreshToken"):
            raise ValueError(
                "claude_cli_credentials must contain claudeAiOauth.accessToken "
                "and claudeAiOauth.refreshToken"
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
    result = await session.execute(select(UserSettings).where(UserSettings.user_id == user_id))
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


def _public_view(overrides: dict[str, Any]) -> dict[str, Any]:
    """Build the credential-free settings view for a set of user overrides.

    Secrets collapse to `<key>_configured` booleans reflecting whether *this
    user* stored one. The instance credential is never represented at all, so
    there is nothing for a response to leak.

    Args:
        overrides: The user's stored `settings_json`.

    Returns:
        Dict of readable settings plus the `*_configured` flags.
    """
    merged = {k: v for k, v in _defaults().items() if k not in SECRET_KEYS}

    for key in ALLOWED_KEYS - SECRET_KEYS - USER_ONLY_KEYS:
        if key in overrides:
            merged[key] = overrides[key]

    # An explicitly chosen provider is entirely the user's own, so these
    # show what they stored rather than what the instance is configured with.
    for key in USER_ONLY_KEYS - SECRET_KEYS:
        merged[key] = overrides.get(key, "")

    # Everyone defaults to "StudyAIO provided", whatever the instance backend is.
    merged["agent_backend"] = overrides.get("agent_backend", STUDYAIO_BACKEND)
    if merged["agent_backend"] not in VALID_BACKENDS:
        merged["agent_backend"] = STUDYAIO_BACKEND

    for key in SECRET_KEYS:
        merged[f"{key}_configured"] = bool(str(overrides.get(key) or "").strip())

    return merged


async def get_user_settings(session: AsyncSession, user_id: str) -> dict[str, Any]:
    """Get the readable settings for a user — no credential values.

    Args:
        session: Database session.
        user_id: User UUID.

    Returns:
        Dict of all readable settings plus `*_configured` booleans.
    """
    user_settings = await _get_or_create_user_settings(session, user_id)
    merged = _public_view(user_settings.settings_json or {})
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
    updates = dict(updates)

    # Handle special non-settings-json keys
    theme = updates.pop("theme", None)
    dashboard_layout = updates.pop("dashboard_layout", None)
    clear_secrets = updates.pop("clear_secrets", None) or []

    # A credential is write-only, so the UI cannot echo the stored value back
    # on the next save. An empty submission therefore has to mean "leave it
    # alone" — otherwise every unrelated edit would wipe the stored key.
    # Removing one is an explicit act: `clear_secrets`.
    for key in SECRET_KEYS:
        if key in updates and not str(updates[key] or "").strip():
            del updates[key]

    for key in clear_secrets:
        if key not in SECRET_KEYS:
            raise ValueError(f"clear_secrets may only name a credential, got '{key}'")

    # Validate remaining settings
    validated: dict[str, Any] = {}
    for key, value in updates.items():
        validated[key] = validate_setting(key, value)

    user_settings = await _get_or_create_user_settings(session, user_id)

    # Update settings_json
    if validated or clear_secrets:
        current = dict(user_settings.settings_json or {})
        current.update(validated)
        for key in clear_secrets:
            current.pop(key, None)
        user_settings.settings_json = current

    # Update theme
    if theme is not None:
        if theme not in ("light", "dark", "system"):
            raise ValueError("theme must be one of: light, dark, system")
        user_settings.theme = theme

    # Update dashboard layout
    if dashboard_layout is not None:
        user_settings.dashboard_layout = dashboard_layout

    user_settings.updated_at = datetime.now(UTC)
    await session.commit()
    logger.info(
        "user_settings_updated",
        user_id=user_id,
        keys=sorted(validated.keys()),
        cleared=sorted(clear_secrets),
    )

    return await get_user_settings(session, user_id)


async def get_effective_setting_async(session: AsyncSession, user_id: str, key: str) -> Any:
    """Get the effective value of a single readable setting for a user.

    Credentials are not readable here: this reads the public view, so a secret
    key returns None rather than a value.

    Args:
        session: Database session.
        user_id: User UUID.
        key: Setting key name.

    Returns:
        The effective value (user override > env default).
    """
    all_settings = await get_user_settings(session, user_id)
    return all_settings.get(key, getattr(settings, key, None))


# ── User agent config helper ──────────────────────────────────────────


# Keys relevant to AI agent configuration
_AGENT_CONFIG_KEYS = {
    "agent_backend",
    "claude_code_path",
    "claude_model",
    "anthropic_api_key",
    "openai_api_key",
    "openai_model",
    "zai_api_key",
    "zai_model",
    "zai_base_url",
    "ollama_base_url",
    "ollama_model",
    "claude_cli_credentials",
}


async def _get_overrides(session: AsyncSession, user_id: str) -> dict[str, Any]:
    """Read a user's stored settings without creating a row.

    Args:
        session: Database session.
        user_id: User UUID.

    Returns:
        The stored `settings_json`, or an empty dict.
    """
    result = await session.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    user_settings = result.scalar_one_or_none()
    if not user_settings:
        return {}
    return user_settings.settings_json or {}


def resolve_backend(overrides: dict[str, Any]) -> str:
    """Resolve which provider a set of overrides selects.

    Args:
        overrides: The user's stored `settings_json`.

    Returns:
        A backend name; `STUDYAIO_BACKEND` when nothing valid is selected.
    """
    backend = overrides.get("agent_backend") or STUDYAIO_BACKEND
    if backend not in VALID_BACKENDS:
        return STUDYAIO_BACKEND
    return backend


async def uses_instance_provider(session: AsyncSession, user_id: str) -> bool:
    """Whether this user's AI spend lands on the operator's credentials.

    The global daily ceiling exists to bound the operator's bill, so it is
    scoped to exactly the users this returns True for. A user on their own key
    costs the operator nothing and is therefore exempt — their per-tier limits
    still apply, as abuse control.

    Args:
        session: Database session.
        user_id: User UUID.

    Returns:
        True when the user is on "StudyAIO provided".
    """
    overrides = await _get_overrides(session, user_id)
    return resolve_backend(overrides) == STUDYAIO_BACKEND


async def get_user_agent_config(session: AsyncSession, user_id: str) -> dict[str, Any] | None:
    """Get the AI config for a user, or None to mean "use the instance".

    Used by pipeline stages and API endpoints to pass per-user credentials to
    the agent factory.

    A returned config never contains an instance credential. `USER_ONLY_KEYS`
    come from the user's own settings or not at all — the factory then refuses
    a selection with nothing behind it rather than quietly spending the
    operator's key, which is what issue #30 was.

    Args:
        session: Database session.
        user_id: User UUID.

    Returns:
        Dict of AI settings when the user runs their own provider; None when
        they are on "StudyAIO provided".
    """
    overrides = await _get_overrides(session, user_id)
    backend = resolve_backend(overrides)
    if backend == STUDYAIO_BACKEND:
        return None

    defaults = _defaults()
    config: dict[str, Any] = {}
    for key in _AGENT_CONFIG_KEYS:
        if key in USER_ONLY_KEYS:
            config[key] = overrides.get(key, "")
        else:
            config[key] = overrides.get(key, defaults.get(key, ""))
    config["agent_backend"] = backend
    return config


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

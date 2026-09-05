"""Tests for the settings service."""

import pytest

from app.services import settings_service


class TestGetAllSettings:
    """Tests for get_all_settings() sync fallback."""

    def test_returns_defaults(self):
        """Returns env-based defaults."""
        result = settings_service.get_all_settings()
        assert "claude_code_path" in result
        assert "claude_model" in result
        assert "classification_confidence_threshold" in result
        assert "flashcard_count_per_week" in result
        assert "quiz_question_count_per_week" in result
        assert "chunk_size_tokens" in result
        assert "chunk_overlap_tokens" in result


class TestValidateSetting:
    """Tests for validate_setting()."""

    def test_unknown_key_raises(self):
        """Unknown setting keys are rejected."""
        with pytest.raises(ValueError, match="Unknown setting"):
            settings_service.validate_setting("nonexistent", "value")

    def test_claude_model_valid(self):
        """Valid model names are accepted."""
        assert settings_service.validate_setting("claude_model", "opus") == "opus"
        assert settings_service.validate_setting("claude_model", "sonnet") == "sonnet"
        assert settings_service.validate_setting("claude_model", "haiku") == "haiku"

    def test_claude_model_invalid(self):
        """Invalid model names are rejected."""
        with pytest.raises(ValueError, match="must be one of"):
            settings_service.validate_setting("claude_model", "gpt4")

    def test_embedding_backend_is_not_a_user_setting(self):
        """embedding_backend is operator-only — the API must not accept it.

        Not merely unimplemented per-user: an instance's vectors share one
        column and are comparable only when one model produced them, so the
        choice cannot be an account's to make (issue #32).
        """
        assert "embedding_backend" not in settings_service.ALLOWED_KEYS
        with pytest.raises(ValueError, match="Unknown setting"):
            settings_service.validate_setting("embedding_backend", "openai")

    def test_claude_code_path_empty_string_raises(self):
        """Empty path string is rejected."""
        with pytest.raises(ValueError, match="non-empty string"):
            settings_service.validate_setting("claude_code_path", "")

    def test_claude_code_path_strips_whitespace(self):
        """Path is stripped of whitespace."""
        assert (
            settings_service.validate_setting("claude_code_path", "  /usr/bin/claude  ")
            == "/usr/bin/claude"
        )

    def test_confidence_threshold_valid_range(self):
        """Threshold within 0-1 is accepted."""
        assert settings_service.validate_setting("classification_confidence_threshold", 0.5) == 0.5
        assert settings_service.validate_setting("classification_confidence_threshold", 0.0) == 0.0
        assert settings_service.validate_setting("classification_confidence_threshold", 1.0) == 1.0

    def test_confidence_threshold_out_of_range(self):
        """Threshold outside 0-1 is rejected."""
        with pytest.raises(ValueError, match="must be >= 0"):
            settings_service.validate_setting("classification_confidence_threshold", -0.1)
        with pytest.raises(ValueError, match="must be <= 1"):
            settings_service.validate_setting("classification_confidence_threshold", 1.5)

    def test_integer_setting_valid(self):
        """Valid integer settings are accepted."""
        assert settings_service.validate_setting("flashcard_count_per_week", 20) == 20

    def test_integer_setting_out_of_range(self):
        """Integer outside bounds is rejected."""
        with pytest.raises(ValueError, match="must be >= 1"):
            settings_service.validate_setting("flashcard_count_per_week", 0)
        with pytest.raises(ValueError, match="must be <= 100"):
            settings_service.validate_setting("flashcard_count_per_week", 200)

    def test_chunk_size_bounds(self):
        """Chunk size respects its bounds."""
        assert settings_service.validate_setting("chunk_size_tokens", 50) == 50
        assert settings_service.validate_setting("chunk_size_tokens", 5000) == 5000
        with pytest.raises(ValueError):
            settings_service.validate_setting("chunk_size_tokens", 10)

    def test_agent_backend_valid(self):
        """Valid agent backends are accepted."""
        assert settings_service.validate_setting("agent_backend", "claude_code") == "claude_code"
        assert (
            settings_service.validate_setting("agent_backend", "anthropic_api") == "anthropic_api"
        )

    def test_agent_backend_invalid(self):
        """Invalid agent backend is rejected."""
        with pytest.raises(ValueError, match="agent_backend must be one of"):
            settings_service.validate_setting("agent_backend", "not_a_backend")

    def test_anthropic_api_key_strips_whitespace(self):
        """API key is stripped of whitespace."""
        assert (
            settings_service.validate_setting("anthropic_api_key", "  sk-ant-xxx  ") == "sk-ant-xxx"
        )

    def test_max_upload_size_mb_bounds(self):
        """Max upload size respects bounds."""
        assert settings_service.validate_setting("max_upload_size_mb", 1) == 1
        assert settings_service.validate_setting("max_upload_size_mb", 1000) == 1000
        with pytest.raises(ValueError):
            settings_service.validate_setting("max_upload_size_mb", 0)


class TestUpdateSettingsSync:
    """Tests for update_settings() sync backward-compat."""

    def test_validates_then_returns_defaults(self):
        """Sync update validates but returns defaults (no DB persistence)."""
        result = settings_service.update_settings({"claude_model": "sonnet"})
        assert "claude_model" in result

    def test_update_invalid_value_raises(self):
        """Invalid values raise ValueError."""
        with pytest.raises(ValueError):
            settings_service.update_settings({"claude_model": "invalid"})


class TestGetEffectiveSetting:
    """Tests for get_effective_setting() sync fallback."""

    def test_returns_default_when_no_override(self):
        """Returns env-based default."""
        result = settings_service.get_effective_setting("claude_model")
        assert result is not None

    def test_returns_none_for_unknown_key(self):
        """Returns None for unknown keys."""
        result = settings_service.get_effective_setting("nonexistent_key_xyz")
        assert result is None


class TestEmbeddingBackendIsOperatorOnly:
    """embedding_backend has no per-user surface left anywhere (issue #32)."""

    def test_absent_from_defaults_and_public_view(self):
        """It is neither a default nor a readable setting."""
        assert "embedding_backend" not in settings_service.get_all_settings()
        assert "embedding_backend" not in settings_service._public_view({})

    def test_a_stale_stored_override_is_not_echoed_back(self):
        """A value left by the old API stays inert rather than resurfacing."""
        view = settings_service._public_view({"embedding_backend": "openai"})
        assert "embedding_backend" not in view

    def test_still_resolvable_as_an_instance_setting(self):
        """Removing the user surface must not remove the operator's knob."""
        from app.config import settings

        assert settings.embedding_backend
        assert settings_service.get_effective_setting("embedding_backend") == (
            settings.embedding_backend
        )

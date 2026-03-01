"""Tests for the settings service."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services import settings_service


@pytest.fixture(autouse=True)
def settings_file(tmp_path):
    """Override the settings JSON path to use a temp dir."""
    settings_path = tmp_path / "settings.json"
    with patch.object(settings_service, "_settings_path", return_value=settings_path):
        yield settings_path


class TestGetAllSettings:
    """Tests for get_all_settings()."""

    def test_returns_defaults_when_no_file(self, settings_file):
        """Returns env-based defaults when no JSON file exists."""
        result = settings_service.get_all_settings()
        assert "claude_code_path" in result
        assert "claude_model" in result
        assert "classification_confidence_threshold" in result
        assert "flashcard_count_per_week" in result
        assert "quiz_question_count_per_week" in result
        assert "chunk_size_tokens" in result
        assert "chunk_overlap_tokens" in result

    def test_merges_overrides_with_defaults(self, settings_file):
        """JSON overrides are merged on top of defaults."""
        settings_file.write_text(json.dumps({"claude_model": "haiku"}))
        result = settings_service.get_all_settings()
        assert result["claude_model"] == "haiku"

    def test_ignores_unknown_keys_in_file(self, settings_file):
        """Keys not in ALLOWED_KEYS are ignored."""
        settings_file.write_text(json.dumps({"unknown_key": "value", "claude_model": "sonnet"}))
        result = settings_service.get_all_settings()
        assert "unknown_key" not in result
        assert result["claude_model"] == "sonnet"

    def test_handles_corrupted_json(self, settings_file):
        """Handles malformed JSON gracefully."""
        settings_file.write_text("not valid json{")
        result = settings_service.get_all_settings()
        # Should still return defaults
        assert "claude_model" in result


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

    def test_claude_code_path_empty_string_raises(self):
        """Empty path string is rejected."""
        with pytest.raises(ValueError, match="non-empty string"):
            settings_service.validate_setting("claude_code_path", "")

    def test_claude_code_path_strips_whitespace(self):
        """Path is stripped of whitespace."""
        assert settings_service.validate_setting("claude_code_path", "  /usr/bin/claude  ") == "/usr/bin/claude"

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


class TestUpdateSettings:
    """Tests for update_settings()."""

    def test_update_persists_to_file(self, settings_file):
        """Updates are written to the JSON file."""
        settings_service.update_settings({"claude_model": "sonnet"})
        saved = json.loads(settings_file.read_text())
        assert saved["claude_model"] == "sonnet"

    def test_update_returns_merged_settings(self, settings_file):
        """Returns complete merged settings after update."""
        result = settings_service.update_settings({"flashcard_count_per_week": 25})
        assert result["flashcard_count_per_week"] == 25
        # Other keys should still be present
        assert "claude_model" in result

    def test_update_merges_with_existing_overrides(self, settings_file):
        """New updates merge with existing overrides in file."""
        settings_file.write_text(json.dumps({"claude_model": "haiku"}))
        settings_service.update_settings({"flashcard_count_per_week": 30})
        saved = json.loads(settings_file.read_text())
        assert saved["claude_model"] == "haiku"
        assert saved["flashcard_count_per_week"] == 30

    def test_update_invalid_value_raises(self, settings_file):
        """Invalid values raise ValueError without writing."""
        with pytest.raises(ValueError):
            settings_service.update_settings({"claude_model": "invalid"})
        # File should not have been created/modified
        assert not settings_file.exists()

    def test_update_creates_parent_dir(self, tmp_path):
        """Creates the parent directory if it doesn't exist."""
        nested = tmp_path / "sub" / "settings.json"
        with patch.object(settings_service, "_settings_path", return_value=nested):
            settings_service.update_settings({"claude_model": "sonnet"})
        assert nested.exists()


class TestGetEffectiveSetting:
    """Tests for get_effective_setting()."""

    def test_returns_default_when_no_override(self, settings_file):
        """Returns env-based default when no override exists."""
        result = settings_service.get_effective_setting("claude_model")
        assert result is not None

    def test_returns_override_when_set(self, settings_file):
        """Returns override value when it exists in JSON file."""
        settings_file.write_text(json.dumps({"claude_model": "haiku"}))
        assert settings_service.get_effective_setting("claude_model") == "haiku"

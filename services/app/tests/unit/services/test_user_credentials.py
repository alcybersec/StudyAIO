"""Tests for per-user credential settings validation and helpers."""

import json

import pytest

from app.services import settings_service


class TestCliCredentialsValidation:
    """Tests for claude_cli_credentials validation."""

    def test_valid_credentials_accepted(self):
        """Valid JSON with required fields is accepted."""
        creds = json.dumps({
            "claudeAiOauth": {
                "accessToken": "my-token",
                "refreshToken": "my-refresh",
            }
        })
        result = settings_service.validate_setting("claude_cli_credentials", creds)
        assert result == creds

    def test_empty_string_clears_credentials(self):
        """Empty string is allowed (clears credentials)."""
        result = settings_service.validate_setting("claude_cli_credentials", "")
        assert result == ""

    def test_whitespace_only_clears_credentials(self):
        """Whitespace-only string is treated as empty."""
        result = settings_service.validate_setting("claude_cli_credentials", "   ")
        assert result == ""

    def test_non_string_raises(self):
        """Non-string value is rejected."""
        with pytest.raises(ValueError, match="must be a JSON string"):
            settings_service.validate_setting("claude_cli_credentials", 123)

    def test_invalid_json_raises(self):
        """Invalid JSON is rejected."""
        with pytest.raises(ValueError, match="must be valid JSON"):
            settings_service.validate_setting("claude_cli_credentials", "{not json}")

    def test_non_object_json_raises(self):
        """JSON array is rejected (must be object)."""
        with pytest.raises(ValueError, match="must be a JSON object"):
            settings_service.validate_setting("claude_cli_credentials", "[1, 2, 3]")

    def test_missing_access_token_raises(self):
        """Missing accessToken is rejected."""
        creds = json.dumps({
            "claudeAiOauth": {
                "refreshToken": "my-refresh",
            }
        })
        with pytest.raises(ValueError, match="accessToken"):
            settings_service.validate_setting("claude_cli_credentials", creds)

    def test_missing_refresh_token_raises(self):
        """Missing refreshToken is rejected."""
        creds = json.dumps({
            "claudeAiOauth": {
                "accessToken": "my-token",
            }
        })
        with pytest.raises(ValueError, match="refreshToken"):
            settings_service.validate_setting("claude_cli_credentials", creds)

    def test_missing_oauth_section_raises(self):
        """Missing claudeAiOauth section entirely is rejected."""
        creds = json.dumps({"someOtherKey": "value"})
        with pytest.raises(ValueError, match="accessToken"):
            settings_service.validate_setting("claude_cli_credentials", creds)

    def test_extra_fields_preserved(self):
        """Extra fields in credentials JSON are preserved."""
        creds_dict = {
            "claudeAiOauth": {
                "accessToken": "my-token",
                "refreshToken": "my-refresh",
                "expiresAt": "2026-12-31T00:00:00Z",
            },
            "apiKey": "some-api-key",
        }
        creds = json.dumps(creds_dict)
        result = settings_service.validate_setting("claude_cli_credentials", creds)
        assert result == creds


class TestCliCredentialsInAllowedKeys:
    """Verify claude_cli_credentials is in ALLOWED_KEYS."""

    def test_key_in_allowed_keys(self):
        """claude_cli_credentials is a recognized setting key."""
        assert "claude_cli_credentials" in settings_service.ALLOWED_KEYS

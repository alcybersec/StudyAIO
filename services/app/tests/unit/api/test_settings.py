"""Tests for the settings API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest

MOCK_SETTINGS = {
    "claude_code_path": "claude",
    "claude_model": "opus",
    "agent_backend": "claude_code",
    "anthropic_api_key": "",
    "claude_cli_credentials": "",
    "classification_confidence_threshold": 0.7,
    "flashcard_count_per_week": 15,
    "quiz_question_count_per_week": 8,
    "chunk_size_tokens": 500,
    "chunk_overlap_tokens": 50,
    "max_upload_size_mb": 50,
    "theme": "system",
    "dashboard_layout": None,
}


@pytest.mark.asyncio
class TestGetSettings:
    """Tests for GET /api/settings."""

    async def test_get_settings_returns_defaults(self, async_client):
        """GET /api/settings returns all setting keys."""
        with patch(
            "app.api.settings.settings_service.get_user_settings",
            new_callable=AsyncMock,
            return_value=MOCK_SETTINGS,
        ):
            response = await async_client.get("/api/settings")

        assert response.status_code == 200
        data = response.json()
        assert data["claude_model"] == "opus"
        assert data["flashcard_count_per_week"] == 15
        assert data["agent_backend"] == "claude_code"
        assert data["theme"] == "system"
        assert data["max_upload_size_mb"] == 50


@pytest.mark.asyncio
class TestUpdateSettings:
    """Tests for PUT /api/settings."""

    async def test_update_settings_success(self, async_client):
        """PUT /api/settings updates and returns merged settings."""
        merged = {**MOCK_SETTINGS, "claude_model": "sonnet"}

        with patch(
            "app.api.settings.settings_service.update_user_settings",
            new_callable=AsyncMock,
            return_value=merged,
        ):
            response = await async_client.put(
                "/api/settings",
                json={"claude_model": "sonnet"},
            )

        assert response.status_code == 200
        assert response.json()["claude_model"] == "sonnet"

    async def test_update_settings_empty_body_returns_400(self, async_client):
        """PUT /api/settings with no fields returns 400."""
        response = await async_client.put("/api/settings", json={})
        assert response.status_code == 400
        assert "No settings provided" in response.json()["detail"]

    async def test_update_settings_invalid_value_returns_422(self, async_client):
        """PUT /api/settings with invalid value returns 422."""
        with patch(
            "app.api.settings.settings_service.update_user_settings",
            new_callable=AsyncMock,
            side_effect=ValueError("claude_model must be one of ['haiku', 'opus', 'sonnet']"),
        ):
            response = await async_client.put(
                "/api/settings",
                json={"claude_model": "gpt4"},
            )

        assert response.status_code == 422
        assert "must be one of" in response.json()["detail"]

    async def test_update_partial_settings(self, async_client):
        """PUT /api/settings only sends provided fields."""
        merged = {**MOCK_SETTINGS, "flashcard_count_per_week": 25}

        with patch(
            "app.api.settings.settings_service.update_user_settings",
            new_callable=AsyncMock,
            return_value=merged,
        ) as mock_update:
            response = await async_client.put(
                "/api/settings",
                json={"flashcard_count_per_week": 25},
            )

        assert response.status_code == 200
        # Verify the user_id and updates were passed correctly
        call_args = mock_update.call_args
        assert call_args[0][1] == "00000000-0000-0000-0000-000000000001"  # user.id
        assert call_args[0][2] == {"flashcard_count_per_week": 25}

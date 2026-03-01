"""Tests for the settings API endpoints."""

from unittest.mock import patch

import pytest


@pytest.mark.asyncio
class TestGetSettings:
    """Tests for GET /api/settings."""

    async def test_get_settings_returns_defaults(self, async_client):
        """GET /api/settings returns all setting keys."""
        mock_settings = {
            "claude_code_path": "claude",
            "claude_model": "opus",
            "classification_confidence_threshold": 0.7,
            "flashcard_count_per_week": 15,
            "quiz_question_count_per_week": 8,
            "chunk_size_tokens": 500,
            "chunk_overlap_tokens": 50,
        }

        with patch(
            "app.api.settings.settings_service.get_all_settings",
            return_value=mock_settings,
        ):
            response = await async_client.get("/api/settings")

        assert response.status_code == 200
        data = response.json()
        assert data["claude_model"] == "opus"
        assert data["flashcard_count_per_week"] == 15
        assert len(data) == 7


@pytest.mark.asyncio
class TestUpdateSettings:
    """Tests for PUT /api/settings."""

    async def test_update_settings_success(self, async_client):
        """PUT /api/settings updates and returns merged settings."""
        merged = {
            "claude_code_path": "claude",
            "claude_model": "sonnet",
            "classification_confidence_threshold": 0.7,
            "flashcard_count_per_week": 15,
            "quiz_question_count_per_week": 8,
            "chunk_size_tokens": 500,
            "chunk_overlap_tokens": 50,
        }

        with patch(
            "app.api.settings.settings_service.update_settings",
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
            "app.api.settings.settings_service.update_settings",
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
        merged = {
            "claude_code_path": "claude",
            "claude_model": "opus",
            "classification_confidence_threshold": 0.7,
            "flashcard_count_per_week": 25,
            "quiz_question_count_per_week": 8,
            "chunk_size_tokens": 500,
            "chunk_overlap_tokens": 50,
        }

        with patch(
            "app.api.settings.settings_service.update_settings",
            return_value=merged,
        ) as mock_update:
            response = await async_client.put(
                "/api/settings",
                json={"flashcard_count_per_week": 25},
            )

        assert response.status_code == 200
        # Verify only the provided key was passed to update_settings
        mock_update.assert_called_once_with({"flashcard_count_per_week": 25})

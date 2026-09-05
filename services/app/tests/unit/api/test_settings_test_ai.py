"""Tests for POST /api/settings/test-ai endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import ClassificationResult


@pytest.mark.asyncio
class TestTestAIEndpoint:
    """Tests for POST /api/settings/test-ai."""

    async def test_test_ai_success(self, async_client):
        """Successful AI test returns ok status."""
        mock_result = ClassificationResult(
            course_code="TEST101",
            week=1,
            title="Test",
            confidence=0.9,
            reasoning="test",
        )

        mock_agent = MagicMock()
        mock_agent.classify_lecture = AsyncMock(return_value=mock_result)

        with (
            patch(
                "app.services.settings_service.get_user_agent_config",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.agents.factory.get_agent",
                return_value=mock_agent,
            ),
            patch(
                "app.services.settings_service.get_effective_setting",
                return_value="claude_code",
            ),
        ):
            response = await async_client.post("/api/settings/test-ai")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        # No per-user config means "StudyAIO provided". Which provider the
        # operator pays for is not named back to the caller.
        assert data["backend"] == "studyaio"
        assert "successful" in data["message"]

    async def test_test_ai_failure_returns_502(self, async_client):
        """Failed AI test returns 502."""
        mock_agent = MagicMock()
        mock_agent.classify_lecture = AsyncMock(side_effect=Exception("Connection refused"))

        with (
            patch(
                "app.services.settings_service.get_user_agent_config",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.agents.factory.get_agent",
                return_value=mock_agent,
            ),
            patch(
                "app.services.settings_service.get_effective_setting",
                return_value="anthropic_api",
            ),
        ):
            response = await async_client.post("/api/settings/test-ai")

        assert response.status_code == 502
        assert "Connection refused" in response.json()["detail"]

    async def test_test_ai_with_user_settings(self, async_client):
        """Test AI uses per-user settings when available."""
        mock_result = ClassificationResult(
            course_code="TEST101",
            week=1,
            title="Test",
            confidence=0.8,
            reasoning="test",
        )

        mock_agent = MagicMock()
        mock_agent.classify_lecture = AsyncMock(return_value=mock_result)

        user_config = {
            "agent_backend": "anthropic_api",
            "anthropic_api_key": "sk-ant-user-key",
        }

        with (
            patch(
                "app.services.settings_service.get_user_agent_config",
                new_callable=AsyncMock,
                return_value=user_config,
            ),
            patch(
                "app.agents.factory.get_agent",
                return_value=mock_agent,
            ) as mock_get_agent,
        ):
            response = await async_client.post("/api/settings/test-ai")

        assert response.status_code == 200
        # Verify factory was called with user settings
        mock_get_agent.assert_called_once_with(user_settings=user_config)
        data = response.json()
        assert data["backend"] == "anthropic_api"

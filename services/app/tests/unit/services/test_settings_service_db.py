"""Tests for DB-backed per-user settings (async functions)."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import settings_service


@pytest.fixture
def mock_session():
    """AsyncMock of AsyncSession."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def mock_user_settings():
    """Mock UserSettings object."""
    us = MagicMock()
    us.user_id = "user-001"
    us.settings_json = {}
    us.theme = "system"
    us.dashboard_layout = None
    us.updated_at = datetime.utcnow()
    return us


USER_ID = "user-001"


@pytest.mark.asyncio
class TestGetUserSettings:
    """Tests for get_user_settings()."""

    async def test_returns_defaults_for_new_user(self, mock_session, mock_user_settings):
        """New user with no overrides gets env defaults."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch.object(
            settings_service, "_get_or_create_user_settings",
            new_callable=AsyncMock, return_value=mock_user_settings,
        ):
            result = await settings_service.get_user_settings(mock_session, USER_ID)

        assert "claude_model" in result
        assert "claude_code_path" in result
        assert result["theme"] == "system"
        assert result["dashboard_layout"] is None

    async def test_overrides_merged_with_defaults(self, mock_session, mock_user_settings):
        """User overrides are merged on top of defaults."""
        mock_user_settings.settings_json = {"claude_model": "haiku", "flashcard_count_per_week": 25}

        with patch.object(
            settings_service, "_get_or_create_user_settings",
            new_callable=AsyncMock, return_value=mock_user_settings,
        ):
            result = await settings_service.get_user_settings(mock_session, USER_ID)

        assert result["claude_model"] == "haiku"
        assert result["flashcard_count_per_week"] == 25
        # Other defaults still present
        assert "chunk_size_tokens" in result

    async def test_theme_from_user_settings(self, mock_session, mock_user_settings):
        """Theme comes from UserSettings object, not settings_json."""
        mock_user_settings.theme = "dark"

        with patch.object(
            settings_service, "_get_or_create_user_settings",
            new_callable=AsyncMock, return_value=mock_user_settings,
        ):
            result = await settings_service.get_user_settings(mock_session, USER_ID)

        assert result["theme"] == "dark"


@pytest.mark.asyncio
class TestUpdateUserSettings:
    """Tests for update_user_settings()."""

    async def test_validates_and_updates(self, mock_session, mock_user_settings):
        """Valid updates are persisted to settings_json."""
        with patch.object(
            settings_service, "_get_or_create_user_settings",
            new_callable=AsyncMock, return_value=mock_user_settings,
        ), patch.object(
            settings_service, "get_user_settings",
            new_callable=AsyncMock, return_value={"claude_model": "sonnet"},
        ):
            result = await settings_service.update_user_settings(
                mock_session, USER_ID, {"claude_model": "sonnet"}
            )

        assert result["claude_model"] == "sonnet"
        mock_session.commit.assert_called_once()

    async def test_theme_update(self, mock_session, mock_user_settings):
        """Theme is updated directly on UserSettings, not in settings_json."""
        with patch.object(
            settings_service, "_get_or_create_user_settings",
            new_callable=AsyncMock, return_value=mock_user_settings,
        ), patch.object(
            settings_service, "get_user_settings",
            new_callable=AsyncMock, return_value={"theme": "dark"},
        ):
            await settings_service.update_user_settings(
                mock_session, USER_ID, {"theme": "dark"}
            )

        assert mock_user_settings.theme == "dark"

    async def test_invalid_theme_raises(self, mock_session, mock_user_settings):
        """Invalid theme value raises ValueError."""
        with patch.object(
            settings_service, "_get_or_create_user_settings",
            new_callable=AsyncMock, return_value=mock_user_settings,
        ), pytest.raises(ValueError, match="theme must be one of"):
            await settings_service.update_user_settings(
                mock_session, USER_ID, {"theme": "invalid"}
            )

    async def test_invalid_setting_raises(self, mock_session, mock_user_settings):
        """Invalid setting key raises ValueError before persisting."""
        with pytest.raises(ValueError, match="Unknown setting"):
            await settings_service.update_user_settings(
                mock_session, USER_ID, {"nonexistent": "value"}
            )


@pytest.mark.asyncio
class TestGetEffectiveSettingAsync:
    """Tests for get_effective_setting_async()."""

    async def test_returns_value_from_user_settings(self, mock_session):
        """Returns user-specific override when set."""
        with patch.object(
            settings_service, "get_user_settings",
            new_callable=AsyncMock,
            return_value={"claude_model": "haiku", "chunk_size_tokens": 500},
        ):
            result = await settings_service.get_effective_setting_async(
                mock_session, USER_ID, "claude_model"
            )

        assert result == "haiku"

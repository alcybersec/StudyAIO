"""The per-user time zone setting (R-023): read-back, validation, lookup helper."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import settings_service

USER_ID = "user-001"


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def stored_settings():
    us = MagicMock()
    us.user_id = USER_ID
    us.settings_json = {}
    us.theme = "system"
    us.language = "en"
    us.content_language = False
    us.timezone = "UTC"
    us.dashboard_layout = None
    us.updated_at = datetime.now(UTC)
    return us


def _patched(stored):
    return (
        patch.object(
            settings_service,
            "_get_or_create_user_settings",
            new_callable=AsyncMock,
            return_value=stored,
        ),
    )


@pytest.mark.asyncio
class TestReadBack:
    async def test_timezone_default_is_utc(self, mock_session, stored_settings):
        with _patched(stored_settings)[0]:
            result = await settings_service.get_user_settings(mock_session, USER_ID)
        assert result["timezone"] == "UTC"

    async def test_stored_timezone_is_returned(self, mock_session, stored_settings):
        stored_settings.timezone = "Pacific/Kiritimati"
        with _patched(stored_settings)[0]:
            result = await settings_service.get_user_settings(mock_session, USER_ID)
        assert result["timezone"] == "Pacific/Kiritimati"


@pytest.mark.asyncio
class TestUpdate:
    async def _update(self, session, stored, updates):
        with (
            _patched(stored)[0],
            patch.object(
                settings_service, "get_user_settings", new_callable=AsyncMock, return_value={}
            ),
        ):
            return await settings_service.update_user_settings(session, USER_ID, updates)

    async def test_valid_timezone_is_stored_on_the_column(self, mock_session, stored_settings):
        await self._update(mock_session, stored_settings, {"timezone": "America/Los_Angeles"})
        assert stored_settings.timezone == "America/Los_Angeles"
        assert "timezone" not in (stored_settings.settings_json or {})

    async def test_invalid_timezone_is_rejected(self, mock_session, stored_settings):
        with pytest.raises(ValueError, match="timezone"):
            await self._update(mock_session, stored_settings, {"timezone": "Mars/Base"})
        assert stored_settings.timezone == "UTC"


@pytest.mark.asyncio
class TestGetUserTimezone:
    async def test_returns_stored_zone(self, mock_session):
        result = MagicMock()
        result.scalar_one_or_none.return_value = MagicMock(timezone="Asia/Tokyo")
        mock_session.execute = AsyncMock(return_value=result)
        assert await settings_service.get_user_timezone(mock_session, USER_ID) == "Asia/Tokyo"

    async def test_no_row_falls_back_to_utc(self, mock_session):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=result)
        assert await settings_service.get_user_timezone(mock_session, USER_ID) == "UTC"

    async def test_query_is_scoped_to_the_user(self, mock_session):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=result)
        await settings_service.get_user_timezone(mock_session, USER_ID)
        assert USER_ID in str(mock_session.execute.await_args.args[0].compile().params.values())

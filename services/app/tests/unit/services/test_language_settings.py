"""Tests for the interface-language setting and its reach into AI output.

Two settings, not one: `language` says which language, `content_language`
says how far it reaches. The toggle is what gates AI output, so a user with
`language='ru'` and the toggle off gets a Russian menu and English summaries —
which is the default every existing account is upgraded into.
"""

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
    """A UserSettings row at its shipped defaults."""
    us = MagicMock()
    us.user_id = USER_ID
    us.settings_json = {}
    us.theme = "system"
    us.language = "en"
    us.content_language = False
    us.dashboard_layout = None
    us.updated_at = datetime.now(UTC)
    return us


def _row(session, value):
    """Point `session.execute` at a single scalar result."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    session.execute = AsyncMock(return_value=result)


class TestSupportedLanguages:
    def test_english_and_russian(self):
        assert sorted(settings_service.SUPPORTED_LANGUAGES) == ["en", "ru"]

    def test_default_is_english(self):
        assert settings_service.DEFAULT_LANGUAGE == "en"
        assert settings_service.DEFAULT_LANGUAGE in settings_service.SUPPORTED_LANGUAGES


@pytest.mark.asyncio
class TestReadBack:
    async def test_settings_include_language_and_toggle(self, mock_session, stored_settings):
        with patch.object(
            settings_service,
            "_get_or_create_user_settings",
            new_callable=AsyncMock,
            return_value=stored_settings,
        ):
            result = await settings_service.get_user_settings(mock_session, USER_ID)

        assert result["language"] == "en"
        assert result["content_language"] is False

    async def test_stored_values_are_returned(self, mock_session, stored_settings):
        stored_settings.language = "ru"
        stored_settings.content_language = True

        with patch.object(
            settings_service,
            "_get_or_create_user_settings",
            new_callable=AsyncMock,
            return_value=stored_settings,
        ):
            result = await settings_service.get_user_settings(mock_session, USER_ID)

        assert result["language"] == "ru"
        assert result["content_language"] is True


@pytest.mark.asyncio
class TestUpdate:
    async def _update(self, session, stored, updates):
        with (
            patch.object(
                settings_service,
                "_get_or_create_user_settings",
                new_callable=AsyncMock,
                return_value=stored,
            ),
            patch.object(
                settings_service,
                "get_user_settings",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            return await settings_service.update_user_settings(session, USER_ID, updates)

    async def test_supported_language_is_stored_on_the_column(self, mock_session, stored_settings):
        await self._update(mock_session, stored_settings, {"language": "ru"})
        assert stored_settings.language == "ru"
        # Not in the JSONB blob: it is a first-class column, like `theme`.
        assert "language" not in (stored_settings.settings_json or {})

    async def test_unsupported_language_is_rejected(self, mock_session, stored_settings):
        """A typo must not reach a prompt as `Write in xx`."""
        with pytest.raises(ValueError, match="language must be one of"):
            await self._update(mock_session, stored_settings, {"language": "xx"})
        assert stored_settings.language == "en"

    async def test_content_toggle_is_stored(self, mock_session, stored_settings):
        await self._update(mock_session, stored_settings, {"content_language": True})
        assert stored_settings.content_language is True

    async def test_content_toggle_must_be_boolean(self, mock_session, stored_settings):
        with pytest.raises(ValueError, match="content_language must be a boolean"):
            await self._update(mock_session, stored_settings, {"content_language": "yes"})

    async def test_language_is_not_an_agent_setting(self, mock_session, stored_settings):
        """It must not be reachable through the generic settings_json path."""
        with pytest.raises(ValueError, match="Unknown setting"):
            settings_service.validate_setting("language", "ru")


@pytest.mark.asyncio
class TestOutputLanguage:
    """`get_user_output_language` — the only thing the agent factory consults."""

    async def test_none_when_toggle_is_off(self, mock_session, stored_settings):
        """The load-bearing case: a Russian interface alone must not translate output."""
        stored_settings.language = "ru"
        stored_settings.content_language = False
        _row(mock_session, stored_settings)

        assert await settings_service.get_user_output_language(mock_session, USER_ID) is None

    async def test_tag_when_toggle_is_on(self, mock_session, stored_settings):
        stored_settings.language = "ru"
        stored_settings.content_language = True
        _row(mock_session, stored_settings)

        assert await settings_service.get_user_output_language(mock_session, USER_ID) == "ru"

    async def test_none_for_english_even_with_toggle_on(self, mock_session, stored_settings):
        """English is the default voice; an explicit directive would add nothing."""
        stored_settings.language = "en"
        stored_settings.content_language = True
        _row(mock_session, stored_settings)

        assert await settings_service.get_user_output_language(mock_session, USER_ID) is None

    async def test_none_when_the_user_has_no_settings_row(self, mock_session):
        _row(mock_session, None)

        assert await settings_service.get_user_output_language(mock_session, USER_ID) is None

    async def test_none_for_an_unsupported_stored_tag(self, mock_session, stored_settings):
        """Defence in depth: a tag that predates validation stays out of prompts."""
        stored_settings.language = "xx"
        stored_settings.content_language = True
        _row(mock_session, stored_settings)

        assert await settings_service.get_user_output_language(mock_session, USER_ID) is None

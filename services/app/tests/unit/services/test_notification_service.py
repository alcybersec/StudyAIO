"""Tests for notification dispatch service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.notification_preference import NotificationPreference
from app.services.notification_service import (
    CHANNELS,
    EVENT_TYPES,
    get_preferences,
    notify,
    seed_default_preferences,
    update_preferences,
)


def _make_mock_session(prefs: list | None = None) -> AsyncMock:
    """Create a mock async session returning preferences."""
    session = AsyncMock()
    result_mock = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = prefs or []
    result_mock.scalars.return_value = scalars_mock
    result_mock.scalar_one_or_none.return_value = None
    result_mock.scalar.return_value = None
    session.execute.return_value = result_mock
    return session


class TestGetPreferences:
    """Tests for get_preferences."""

    @pytest.mark.asyncio
    async def test_returns_preferences(self) -> None:
        """get_preferences returns list of preference records."""
        pref = NotificationPreference(
            id="p1",
            user_id="user-1",
            channel="email",
            event_type="cards_due",
            enabled=True,
        )
        session = _make_mock_session(prefs=[pref])
        result = await get_preferences(session, "user-1")
        assert len(result) == 1
        assert result[0].channel == "email"


class TestUpdatePreferences:
    """Tests for update_preferences."""

    @pytest.mark.asyncio
    async def test_update_creates_new_preference(self) -> None:
        """update_preferences creates new pref if not existing."""
        session = _make_mock_session(prefs=[])
        # execute returns different things for different queries
        result_none = MagicMock()
        result_none.scalar_one_or_none.return_value = None
        result_empty = MagicMock()
        scalars_empty = MagicMock()
        scalars_empty.all.return_value = []
        result_empty.scalars.return_value = scalars_empty

        session.execute.side_effect = [result_none, result_empty]

        await update_preferences(
            session,
            "user-1",
            [{"channel": "email", "event_type": "cards_due", "enabled": True}],
        )
        session.add.assert_called_once()


class TestSeedDefaultPreferences:
    """Tests for seed_default_preferences."""

    @pytest.mark.asyncio
    async def test_seeds_defaults_when_empty(self) -> None:
        """seed_default_preferences creates all channel×event combinations."""
        session = _make_mock_session(prefs=[])
        result = await seed_default_preferences(session, "user-1")
        expected_count = len(CHANNELS) * len(EVENT_TYPES)
        assert len(result) == expected_count
        assert session.add.call_count == expected_count

    @pytest.mark.asyncio
    async def test_no_op_when_prefs_exist(self) -> None:
        """seed_default_preferences returns existing prefs without adding."""
        existing = [
            NotificationPreference(
                id="p1",
                user_id="user-1",
                channel="email",
                event_type="cards_due",
                enabled=True,
            )
        ]
        session = _make_mock_session(prefs=existing)
        result = await seed_default_preferences(session, "user-1")
        assert len(result) == 1
        session.add.assert_not_called()


class TestNotify:
    """Tests for the notify dispatcher."""

    @pytest.mark.asyncio
    async def test_noop_when_notifications_disabled(self) -> None:
        """notify returns empty dict when notifications_enabled=False."""
        with patch("app.services.notification_service.settings") as mock_settings:
            mock_settings.notifications_enabled = False
            session = _make_mock_session()
            result = await notify(session, "user-1", "cards_due", due_count=5)
            assert result == {}

    @pytest.mark.asyncio
    async def test_dispatch_to_email(self) -> None:
        """notify dispatches to email when preference is enabled."""
        pref = NotificationPreference(
            id="p1",
            user_id="user-1",
            channel="email",
            event_type="cards_due",
            enabled=True,
        )
        session = AsyncMock()

        # First execute: get enabled prefs
        prefs_result = MagicMock()
        prefs_scalars = MagicMock()
        prefs_scalars.all.return_value = [pref]
        prefs_result.scalars.return_value = prefs_scalars

        # Second execute: get user email
        email_result = MagicMock()
        email_result.scalar_one_or_none.return_value = "user@test.com"

        session.execute.side_effect = [prefs_result, email_result]

        with (
            patch("app.services.notification_service.settings") as mock_settings,
            patch("app.services.email_service.send_cards_due", new_callable=AsyncMock) as mock_send,
        ):
            mock_settings.notifications_enabled = True
            mock_send.return_value = True
            result = await notify(session, "user-1", "cards_due", due_count=5)
            assert result.get("email") is True

    @pytest.mark.asyncio
    async def test_dispatch_to_telegram(self) -> None:
        """notify dispatches to telegram when preference is enabled."""
        from app.models.telegram_link import TelegramLink

        pref = NotificationPreference(
            id="p1",
            user_id="user-1",
            channel="telegram",
            event_type="cards_due",
            enabled=True,
        )
        link = TelegramLink(
            id="l1",
            user_id="user-1",
            chat_id=12345,
            verified=True,
        )

        session = AsyncMock()

        # First execute: get enabled prefs
        prefs_result = MagicMock()
        prefs_scalars = MagicMock()
        prefs_scalars.all.return_value = [pref]
        prefs_result.scalars.return_value = prefs_scalars

        # Second execute: get telegram link
        link_result = MagicMock()
        link_result.scalar_one_or_none.return_value = link

        session.execute.side_effect = [prefs_result, link_result]

        with (
            patch("app.services.notification_service.settings") as mock_settings,
            patch(
                "app.services.telegram_service.send_cards_due", new_callable=AsyncMock
            ) as mock_send,
        ):
            mock_settings.notifications_enabled = True
            mock_send.return_value = True
            result = await notify(session, "user-1", "cards_due", due_count=5)
            assert result.get("telegram") is True

    @pytest.mark.asyncio
    async def test_best_effort_on_failure(self) -> None:
        """notify catches exceptions and returns False for failed channels."""
        pref = NotificationPreference(
            id="p1",
            user_id="user-1",
            channel="email",
            event_type="cards_due",
            enabled=True,
        )
        session = AsyncMock()

        prefs_result = MagicMock()
        prefs_scalars = MagicMock()
        prefs_scalars.all.return_value = [pref]
        prefs_result.scalars.return_value = prefs_scalars

        email_result = MagicMock()
        email_result.scalar_one_or_none.return_value = "user@test.com"

        session.execute.side_effect = [prefs_result, email_result]

        with (
            patch("app.services.notification_service.settings") as mock_settings,
            patch("app.services.email_service.send_cards_due", new_callable=AsyncMock) as mock_send,
        ):
            mock_settings.notifications_enabled = True
            mock_send.side_effect = RuntimeError("SMTP down")
            result = await notify(session, "user-1", "cards_due", due_count=5)
            assert result.get("email") is False

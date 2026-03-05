"""Tests for notification-related models."""

from app.models.notification_preference import NotificationPreference
from app.models.telegram_link import TelegramLink


class TestNotificationPreference:
    """Tests for NotificationPreference model."""

    def test_create_notification_preference(self) -> None:
        """NotificationPreference can be instantiated with required fields."""
        pref = NotificationPreference(
            id="test-id",
            user_id="user-1",
            channel="email",
            event_type="pipeline_complete",
            enabled=True,
        )
        assert pref.user_id == "user-1"
        assert pref.channel == "email"
        assert pref.event_type == "pipeline_complete"
        assert pref.enabled is True

    def test_notification_preference_tablename(self) -> None:
        """NotificationPreference has correct table name."""
        assert NotificationPreference.__tablename__ == "notification_preferences"


class TestTelegramLink:
    """Tests for TelegramLink model."""

    def test_create_telegram_link(self) -> None:
        """TelegramLink can be instantiated with required fields."""
        link = TelegramLink(
            id="test-id",
            user_id="user-1",
            chat_id=123456789,
            username="testuser",
            verified=True,
            link_token="abc123token",
        )
        assert link.user_id == "user-1"
        assert link.chat_id == 123456789
        assert link.username == "testuser"
        assert link.verified is True
        assert link.link_token == "abc123token"

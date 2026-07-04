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


class TestNotification:
    """Tests for the inbox Notification model."""

    def test_create_notification(self) -> None:
        """Notification can be instantiated with required fields."""
        from app.models.notification import Notification

        notification = Notification(
            id="notif-1",
            user_id="user-1",
            kind="pipeline",
            title="lecture.pdf processed",
            body="12 flashcards and 6 quiz questions generated.",
            href="/courses/CSIT302/weeks/5",
        )
        assert notification.user_id == "user-1"
        assert notification.kind == "pipeline"
        assert notification.title == "lecture.pdf processed"
        assert notification.href == "/courses/CSIT302/weeks/5"
        assert notification.read_at is None

    def test_notification_tablename(self) -> None:
        """Notification has correct table name."""
        from app.models.notification import Notification

        assert Notification.__tablename__ == "notifications"

    def test_notification_optional_fields(self) -> None:
        """body and href are optional."""
        from app.models.notification import Notification

        notification = Notification(
            id="notif-2",
            user_id="user-1",
            kind="review",
            title="Review needed",
        )
        assert notification.body is None
        assert notification.href is None

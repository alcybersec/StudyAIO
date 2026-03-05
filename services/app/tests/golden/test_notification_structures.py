"""Golden tests for notification response structures.

Validates that notification-related data conforms to expected schemas:
- Notification preferences response: channel × event_type grid
- Telegram link response: deep link URL format
"""

import pytest

from app.services.notification_service import CHANNELS, EVENT_TYPES


# ── Sample data fixtures ────────────────────────────────────────────


@pytest.fixture
def sample_preferences_response():
    """A realistic notification preferences response."""
    return {
        "preferences": [
            {
                "channel": "email",
                "event_type": "pipeline_complete",
                "enabled": True,
            },
            {
                "channel": "email",
                "event_type": "cards_due",
                "enabled": False,
            },
            {
                "channel": "telegram",
                "event_type": "pipeline_complete",
                "enabled": True,
            },
            {
                "channel": "telegram",
                "event_type": "cards_due",
                "enabled": True,
            },
        ],
    }


@pytest.fixture
def sample_telegram_link_response():
    """A realistic Telegram link response."""
    return {
        "link_token": "abc123tokenvalue",
        "bot_username": "StudyAIOBot",
        "deep_link": "https://t.me/StudyAIOBot?start=abc123tokenvalue",
    }


# ── Preference structure tests ──────────────────────────────────────


class TestNotificationPreferencesStructure:
    """Validate notification preferences response structure."""

    def test_preferences_response_has_list(self, sample_preferences_response) -> None:
        """Response contains a 'preferences' list."""
        assert "preferences" in sample_preferences_response
        assert isinstance(sample_preferences_response["preferences"], list)
        assert len(sample_preferences_response["preferences"]) > 0

    def test_preference_item_fields(self, sample_preferences_response) -> None:
        """Each preference item has channel, event_type, enabled."""
        required_fields = {"channel", "event_type", "enabled"}
        for item in sample_preferences_response["preferences"]:
            assert required_fields.issubset(item.keys()), (
                f"Missing fields: {required_fields - set(item.keys())}"
            )

    def test_preference_channels_valid(self, sample_preferences_response) -> None:
        """All channels are from the valid set."""
        for item in sample_preferences_response["preferences"]:
            assert item["channel"] in CHANNELS, (
                f"Invalid channel: {item['channel']}"
            )

    def test_preference_event_types_valid(self, sample_preferences_response) -> None:
        """All event_types are from the valid set."""
        for item in sample_preferences_response["preferences"]:
            assert item["event_type"] in EVENT_TYPES, (
                f"Invalid event_type: {item['event_type']}"
            )

    def test_preference_enabled_is_bool(self, sample_preferences_response) -> None:
        """The enabled field is a boolean."""
        for item in sample_preferences_response["preferences"]:
            assert isinstance(item["enabled"], bool)

    def test_event_types_closed_set(self) -> None:
        """EVENT_TYPES is the expected closed set."""
        expected = {
            "pipeline_complete",
            "review_created",
            "cards_due",
            "exam_reminder",
            "weekly_digest",
        }
        assert set(EVENT_TYPES) == expected

    def test_channels_closed_set(self) -> None:
        """CHANNELS is the expected closed set."""
        expected = {"email", "telegram"}
        assert set(CHANNELS) == expected


# ── Telegram link structure tests ───────────────────────────────────


class TestTelegramLinkStructure:
    """Validate Telegram link response structure."""

    def test_telegram_link_fields(self, sample_telegram_link_response) -> None:
        """Response has link_token, bot_username, deep_link."""
        required_fields = {"link_token", "bot_username", "deep_link"}
        assert required_fields.issubset(sample_telegram_link_response.keys())

    def test_deep_link_format(self, sample_telegram_link_response) -> None:
        """Deep link URL starts with https://t.me/ and contains start param."""
        deep_link = sample_telegram_link_response["deep_link"]
        assert deep_link.startswith("https://t.me/")
        assert "?start=" in deep_link

    def test_link_token_present(self, sample_telegram_link_response) -> None:
        """Link token is a non-empty string."""
        token = sample_telegram_link_response["link_token"]
        assert isinstance(token, str)
        assert len(token) > 0

    def test_deep_link_contains_token(self, sample_telegram_link_response) -> None:
        """Deep link URL contains the link token."""
        token = sample_telegram_link_response["link_token"]
        deep_link = sample_telegram_link_response["deep_link"]
        assert token in deep_link

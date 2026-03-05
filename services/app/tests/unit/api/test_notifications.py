"""Tests for notification API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.notification_preference import NotificationPreference
from app.models.telegram_link import TelegramLink


@pytest.fixture
async def notif_client(mock_session, default_test_user):
    """Async client for notification API tests."""
    import httpx

    from app.api.deps import get_current_user_or_default
    from app.core.database import get_session
    from app.core.rate_limit import limiter
    from app.main import app

    async def override_session():
        yield mock_session

    async def override_user():
        return default_test_user

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user_or_default] = override_user
    limiter.reset()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.clear()


class TestGetPreferences:
    """Tests for GET /api/notifications/preferences."""

    @pytest.mark.asyncio
    async def test_get_preferences_seeds_defaults(self, notif_client) -> None:
        """Returns seeded defaults when no preferences exist."""
        with patch(
            "app.api.notifications.notification_service.get_preferences",
            new_callable=AsyncMock,
        ) as mock_get, patch(
            "app.api.notifications.notification_service.seed_default_preferences",
            new_callable=AsyncMock,
        ) as mock_seed:
            mock_get.return_value = []
            mock_seed.return_value = [
                NotificationPreference(
                    id="p1", user_id="u1", channel="email",
                    event_type="cards_due", enabled=False,
                ),
            ]
            response = await notif_client.get("/api/notifications/preferences")
            assert response.status_code == 200
            data = response.json()
            assert "preferences" in data
            assert len(data["preferences"]) == 1

    @pytest.mark.asyncio
    async def test_get_preferences_returns_existing(self, notif_client) -> None:
        """Returns existing preferences without seeding."""
        prefs = [
            NotificationPreference(
                id="p1", user_id="u1", channel="email",
                event_type="cards_due", enabled=True,
            ),
            NotificationPreference(
                id="p2", user_id="u1", channel="telegram",
                event_type="cards_due", enabled=False,
            ),
        ]
        with patch(
            "app.api.notifications.notification_service.get_preferences",
            new_callable=AsyncMock,
            return_value=prefs,
        ):
            response = await notif_client.get("/api/notifications/preferences")
            assert response.status_code == 200
            data = response.json()
            assert len(data["preferences"]) == 2


class TestUpdatePreferences:
    """Tests for PUT /api/notifications/preferences."""

    @pytest.mark.asyncio
    async def test_update_preferences(self, notif_client) -> None:
        """Updates preferences and returns updated list."""
        updated = [
            NotificationPreference(
                id="p1", user_id="u1", channel="email",
                event_type="cards_due", enabled=True,
            ),
        ]
        with patch(
            "app.api.notifications.notification_service.update_preferences",
            new_callable=AsyncMock,
            return_value=updated,
        ):
            response = await notif_client.put(
                "/api/notifications/preferences",
                json={
                    "preferences": [
                        {"channel": "email", "event_type": "cards_due", "enabled": True},
                    ]
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["preferences"][0]["enabled"] is True


class TestTelegramLink:
    """Tests for Telegram link/unlink endpoints."""

    @pytest.mark.asyncio
    async def test_generate_telegram_link(self, notif_client) -> None:
        """POST /telegram/link returns deep link URL."""
        with (
            patch("app.api.notifications.settings") as mock_settings,
            patch(
                "app.api.notifications.telegram_service.generate_link_token",
                new_callable=AsyncMock,
                return_value="test-token-123",
            ),
        ):
            mock_settings.telegram_bot_token.get_secret_value.return_value = "123:abc"
            mock_settings.telegram_webhook_url = "StudyAIOBot"
            response = await notif_client.post("/api/notifications/telegram/link")
            assert response.status_code == 200
            data = response.json()
            assert data["link_token"] == "test-token-123"
            assert "t.me" in data["deep_link"]

    @pytest.mark.asyncio
    async def test_unlink_telegram(self, notif_client) -> None:
        """DELETE /telegram/unlink returns unlinked status."""
        with patch(
            "app.api.notifications.telegram_service.unlink",
            new_callable=AsyncMock,
            return_value=True,
        ):
            response = await notif_client.delete("/api/notifications/telegram/unlink")
            assert response.status_code == 200
            data = response.json()
            assert data["linked"] is False


class TestTelegramWebhook:
    """Tests for POST /api/notifications/telegram/webhook."""

    @pytest.mark.asyncio
    async def test_webhook_valid(self, notif_client) -> None:
        """Webhook processes valid update."""
        with (
            patch("app.api.notifications.settings") as mock_settings,
            patch(
                "app.api.notifications.telegram_service.handle_telegram_webhook",
                new_callable=AsyncMock,
                return_value="Linked!",
            ),
        ):
            mock_settings.telegram_webhook_url = ""
            response = await notif_client.post(
                "/api/notifications/telegram/webhook",
                json={"message": {"text": "/start token", "chat": {"id": 123}, "from": {}}},
            )
            assert response.status_code == 200
            assert response.json()["ok"] is True

    @pytest.mark.asyncio
    async def test_webhook_invalid_secret(self, notif_client) -> None:
        """Webhook rejects request with wrong secret."""
        with patch("app.api.notifications.settings") as mock_settings:
            mock_settings.telegram_webhook_url = "correct-secret"
            response = await notif_client.post(
                "/api/notifications/telegram/webhook",
                json={"message": {}},
                headers={"x-telegram-bot-api-secret-token": "wrong-secret"},
            )
            assert response.status_code == 403


class TestTestNotification:
    """Tests for POST /api/notifications/test."""

    @pytest.mark.asyncio
    async def test_send_test_email(self, notif_client, default_test_user) -> None:
        """Test notification sends email successfully."""
        with patch(
            "app.services.email_service.send_email",
            new_callable=AsyncMock,
            return_value=True,
        ):
            response = await notif_client.post(
                "/api/notifications/test",
                json={"channel": "email"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["channel"] == "email"

"""Tests for notification API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest

from app.config import settings
from app.models.notification_preference import NotificationPreference


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
        with (
            patch(
                "app.api.notifications.notification_service.get_preferences",
                new_callable=AsyncMock,
            ) as mock_get,
            patch(
                "app.api.notifications.notification_service.seed_default_preferences",
                new_callable=AsyncMock,
            ) as mock_seed,
        ):
            mock_get.return_value = []
            mock_seed.return_value = [
                NotificationPreference(
                    id="p1",
                    user_id="u1",
                    channel="email",
                    event_type="cards_due",
                    enabled=False,
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
                id="p1",
                user_id="u1",
                channel="email",
                event_type="cards_due",
                enabled=True,
            ),
            NotificationPreference(
                id="p2",
                user_id="u1",
                channel="telegram",
                event_type="cards_due",
                enabled=False,
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
                id="p1",
                user_id="u1",
                channel="email",
                event_type="cards_due",
                enabled=True,
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
    """Tests for POST /api/notifications/telegram/webhook (SEC-015)."""

    URL = "/api/notifications/telegram/webhook"
    HEADER = "x-telegram-bot-api-secret-token"
    SECRET = "s3cret-value_ABC"
    BODY = {"message": {"text": "/start token", "chat": {"id": 123}, "from": {}}}

    @pytest.fixture(autouse=True)
    def _reset_warning(self):
        from app.api import notifications

        notifications._unset_secret_warned = False
        yield
        notifications._unset_secret_warned = False

    @pytest.fixture
    def handler(self):
        with patch(
            "app.api.notifications.telegram_service.handle_telegram_webhook",
            new_callable=AsyncMock,
            return_value="Linked!",
        ) as mock:
            yield mock

    @pytest.fixture
    def secret_set(self):
        from pydantic import SecretStr

        with (
            patch.object(settings, "telegram_webhook_secret", SecretStr(self.SECRET)),
            patch.object(settings, "single_user_mode", False),
        ):
            yield

    @pytest.mark.asyncio
    async def test_correct_secret_is_handled(self, notif_client, handler, secret_set) -> None:
        response = await notif_client.post(
            self.URL, json=self.BODY, headers={self.HEADER: self.SECRET}
        )
        assert response.status_code == 200
        assert response.json()["ok"] is True
        handler.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_wrong_secret_rejected_without_side_effects(
        self, notif_client, handler, secret_set
    ) -> None:
        response = await notif_client.post(
            self.URL, json=self.BODY, headers={self.HEADER: "wrong-secret"}
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Invalid webhook secret"}
        handler.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_missing_header_rejected(self, notif_client, handler, secret_set) -> None:
        response = await notif_client.post(self.URL, json=self.BODY)
        assert response.status_code == 403
        assert response.json() == {"detail": "Invalid webhook secret"}
        handler.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_webhook_url_is_not_accepted_as_secret(
        self, notif_client, handler, secret_set
    ) -> None:
        url = "https://studyaio.example.com/api/notifications/telegram/webhook"
        with patch.object(settings, "telegram_webhook_url", url):
            response = await notif_client.post(self.URL, json=self.BODY, headers={self.HEADER: url})
        assert response.status_code == 403
        handler.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_compare_is_constant_time(self, notif_client, handler, secret_set) -> None:
        with patch("app.api.notifications.hmac.compare_digest", return_value=False) as compare:
            response = await notif_client.post(
                self.URL, json=self.BODY, headers={self.HEADER: self.SECRET}
            )
        compare.assert_called_once()
        assert response.status_code == 403
        handler.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unset_secret_multi_user_rejects_everything(self, notif_client, handler) -> None:
        from pydantic import SecretStr

        with (
            patch.object(settings, "telegram_webhook_secret", SecretStr("")),
            patch.object(settings, "single_user_mode", False),
        ):
            for hdr in ({}, {self.HEADER: ""}, {self.HEADER: "anything"}):
                response = await notif_client.post(self.URL, json=self.BODY, headers=hdr)
                assert response.status_code == 403
                assert response.json() == {"detail": "Invalid webhook secret"}
        handler.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unset_secret_warns_once_without_value(self, notif_client, handler) -> None:
        from pydantic import SecretStr

        with (
            patch.object(settings, "telegram_webhook_secret", SecretStr("")),
            patch.object(settings, "single_user_mode", False),
            patch("app.api.notifications.logger") as log,
        ):
            for _ in range(3):
                await notif_client.post(self.URL, json=self.BODY, headers={self.HEADER: "x"})
        assert log.warning.call_count == 1
        assert "x" not in log.warning.call_args.kwargs.values()


class TestTelegramWebhookSecretConfig:
    def test_secret_defaults_empty_and_is_secretstr(self) -> None:
        from pydantic import SecretStr

        from app.config import Settings

        field = Settings.model_fields["telegram_webhook_secret"]
        assert field.annotation is SecretStr
        assert field.default.get_secret_value() == ""


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

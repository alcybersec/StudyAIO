"""Tests for Web Push notification API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.push_subscription import PushSubscription


@pytest.fixture
async def push_client(mock_session, default_test_user):
    """Async client for push notification API tests."""
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


class TestGetVapidKey:
    """Tests for GET /api/notifications/push/vapid-key."""

    @pytest.mark.asyncio
    async def test_get_vapid_key(self, push_client) -> None:
        """Returns VAPID public key when configured."""
        with patch("app.api.notifications.settings") as mock_settings:
            mock_settings.vapid_public_key = "BPtest-vapid-public-key-base64"
            response = await push_client.get("/api/notifications/push/vapid-key")

        assert response.status_code == 200
        data = response.json()
        assert data["public_key"] == "BPtest-vapid-public-key-base64"

    @pytest.mark.asyncio
    async def test_get_vapid_key_not_configured(self, push_client) -> None:
        """Returns 400 when VAPID public key is not configured."""
        with patch("app.api.notifications.settings") as mock_settings:
            mock_settings.vapid_public_key = ""
            response = await push_client.get("/api/notifications/push/vapid-key")

        assert response.status_code == 400
        assert "not configured" in response.json()["detail"].lower()


class TestPushSubscribe:
    """Tests for POST /api/notifications/push/subscribe."""

    @pytest.mark.asyncio
    async def test_subscribe_push(self, push_client) -> None:
        """Successfully subscribes to push notifications."""
        mock_sub = MagicMock(spec=PushSubscription)
        mock_sub.id = "sub-001"

        with patch(
            "app.api.notifications.push_service.subscribe",
            new_callable=AsyncMock,
            return_value=mock_sub,
        ):
            response = await push_client.post(
                "/api/notifications/push/subscribe",
                json={
                    "endpoint": "https://push.example.com/send/abc123",
                    "p256dh": "test-p256dh-key",
                    "auth": "test-auth-secret",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "sub-001"
        assert "subscribed" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_subscribe_push_missing_fields(self, push_client) -> None:
        """Returns 422 when required fields are missing."""
        # Missing p256dh and auth
        response = await push_client.post(
            "/api/notifications/push/subscribe",
            json={
                "endpoint": "https://push.example.com/send/abc123",
            },
        )

        assert response.status_code == 422


class TestPushUnsubscribe:
    """Tests for DELETE /api/notifications/push/unsubscribe."""

    @pytest.mark.asyncio
    async def test_unsubscribe_push(self, push_client) -> None:
        """Successfully unsubscribes from push notifications."""
        with patch(
            "app.api.notifications.push_service.unsubscribe",
            new_callable=AsyncMock,
            return_value=True,
        ):
            response = await push_client.request(
                "DELETE",
                "/api/notifications/push/unsubscribe",
                json={
                    "endpoint": "https://push.example.com/send/abc123",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "unsubscribed" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_unsubscribe_push_not_found(self, push_client) -> None:
        """Returns 404 when subscription not found."""
        with patch(
            "app.api.notifications.push_service.unsubscribe",
            new_callable=AsyncMock,
            return_value=False,
        ):
            response = await push_client.request(
                "DELETE",
                "/api/notifications/push/unsubscribe",
                json={
                    "endpoint": "https://push.example.com/nonexistent",
                },
            )

        assert response.status_code == 404

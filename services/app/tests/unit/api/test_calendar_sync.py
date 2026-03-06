"""Tests for calendar sync API endpoints."""

import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


@pytest.fixture
async def cal_client(mock_session, default_test_user):
    """Async client for calendar API tests."""
    from app.api.deps import get_current_user, get_current_user_or_default
    from app.core.database import get_session
    from app.core.rate_limit import limiter
    from app.main import app

    async def override_session():
        yield mock_session

    async def override_user():
        return default_test_user

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user_or_default] = override_user
    app.dependency_overrides[get_current_user] = override_user

    limiter.reset()

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.config.settings.data_dir", tmpdir):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                yield client

    app.dependency_overrides.clear()


class TestConnectEndpoint:
    """Tests for POST /api/calendar/connect."""

    @pytest.mark.asyncio
    async def test_connect_endpoint(self, cal_client):
        """Connect endpoint calls service and returns sync info."""
        mock_sync = MagicMock()
        mock_sync.id = "sync-001"
        mock_sync.google_calendar_id = "cal@group.calendar.google.com"

        with patch(
            "app.api.calendar_sync.gcal_service.connect_google_calendar",
            new_callable=AsyncMock,
            return_value=mock_sync,
        ):
            response = await cal_client.post(
                "/api/calendar/connect",
                json={"auth_code": "test-code"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["sync_id"] == "sync-001"
        assert data["calendar_id"] == "cal@group.calendar.google.com"


class TestStatusEndpoint:
    """Tests for GET /api/calendar/status."""

    @pytest.mark.asyncio
    async def test_status_endpoint_returns_calendars(self, cal_client):
        """Status endpoint returns list of connected calendars."""
        with patch(
            "app.api.calendar_sync.gcal_service.get_sync_status",
            new_callable=AsyncMock,
            return_value=[
                {
                    "id": "sync-001",
                    "google_calendar_id": "cal@group.calendar.google.com",
                    "sync_direction": "push",
                    "last_synced_at": "2026-03-06T12:00:00",
                    "event_count": 5,
                }
            ],
        ):
            response = await cal_client.get("/api/calendar/status")

        assert response.status_code == 200
        data = response.json()
        assert len(data["calendars"]) == 1
        assert data["calendars"][0]["event_count"] == 5


class TestDisconnectEndpoint:
    """Tests for DELETE /api/calendar/disconnect/{sync_id}."""

    @pytest.mark.asyncio
    async def test_disconnect_endpoint(self, cal_client):
        """Disconnect endpoint calls service."""
        with patch(
            "app.api.calendar_sync.gcal_service.disconnect_calendar",
            new_callable=AsyncMock,
            return_value=True,
        ):
            response = await cal_client.delete("/api/calendar/disconnect/sync-001")

        assert response.status_code == 200
        assert response.json()["detail"] == "Calendar disconnected"


class TestSyncEndpoint:
    """Tests for POST /api/calendar/sync."""

    @pytest.mark.asyncio
    async def test_sync_endpoint(self, cal_client):
        """Sync endpoint triggers sync and returns results."""
        with patch(
            "app.api.calendar_sync.gcal_service.get_sync_status",
            new_callable=AsyncMock,
            return_value=[{"id": "sync-001"}],
        ), patch(
            "app.api.calendar_sync.gcal_service.sync_calendar",
            new_callable=AsyncMock,
            return_value={"pushed": 3, "pulled": 1},
        ):
            response = await cal_client.post("/api/calendar/sync")

        assert response.status_code == 200
        data = response.json()
        assert data["pushed"] == 3
        assert data["pulled"] == 1


class TestWebhookEndpoint:
    """Tests for POST /api/calendar/webhook."""

    @pytest.mark.asyncio
    async def test_webhook_endpoint(self, cal_client):
        """Webhook endpoint processes Google push notifications."""
        with patch(
            "app.api.calendar_sync.gcal_service.handle_gcal_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook:
            response = await cal_client.post(
                "/api/calendar/webhook",
                headers={
                    "x-goog-channel-id": "sync-001",
                    "x-goog-resource-id": "resource-123",
                },
            )

        assert response.status_code == 200
        mock_webhook.assert_awaited_once_with(
            mock_webhook.call_args[0][0],  # session
            "sync-001",
            "resource-123",
        )

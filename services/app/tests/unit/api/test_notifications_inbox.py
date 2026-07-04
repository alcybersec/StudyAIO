"""Tests for the notification inbox API endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_notification(
    id: str = "notif-1",
    kind: str = "pipeline",
    title: str = "lecture.pdf processed",
    read_at: datetime | None = None,
    created_at: datetime | None = None,
) -> MagicMock:
    n = MagicMock()
    n.id = id
    n.user_id = "00000000-0000-0000-0000-000000000001"
    n.kind = kind
    n.title = title
    n.body = None
    n.href = "/courses/CSIT302/weeks/5"
    n.read_at = read_at
    n.created_at = created_at or datetime(2026, 7, 1, tzinfo=UTC)
    return n


@pytest.mark.asyncio
class TestListNotifications:
    """Tests for GET /api/notifications."""

    async def test_list_returns_newest_first(self, async_client):
        """Notifications come back in the order the service provides (newest first)."""
        newer = _make_notification(id="n2", created_at=datetime(2026, 7, 2, tzinfo=UTC))
        older = _make_notification(id="n1", created_at=datetime(2026, 7, 1, tzinfo=UTC))
        with patch(
            "app.api.notifications_inbox.notification_service.list_inbox_notifications",
            new_callable=AsyncMock,
            return_value=[newer, older],
        ) as mock_list:
            response = await async_client.get("/api/notifications")

        assert response.status_code == 200
        data = response.json()
        assert [n["id"] for n in data] == ["n2", "n1"]
        _, kwargs = mock_list.call_args
        assert kwargs.get("unread_only") is False

    async def test_list_unread_filter(self, async_client):
        """?unread=true is forwarded to the service."""
        with patch(
            "app.api.notifications_inbox.notification_service.list_inbox_notifications",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_list:
            response = await async_client.get("/api/notifications", params={"unread": "true"})

        assert response.status_code == 200
        _, kwargs = mock_list.call_args
        assert kwargs.get("unread_only") is True


@pytest.mark.asyncio
class TestMarkRead:
    """Tests for POST /api/notifications/mark-read."""

    async def test_mark_read_returns_updated_count(self, async_client):
        """Marking notifications read returns the number updated."""
        with patch(
            "app.api.notifications_inbox.notification_service.mark_notifications_read",
            new_callable=AsyncMock,
            return_value=2,
        ) as mock_mark:
            response = await async_client.post(
                "/api/notifications/mark-read", json={"ids": ["n1", "n2"]}
            )

        assert response.status_code == 200
        assert response.json()["updated"] == 2
        args = mock_mark.call_args.args
        assert args[1] == "00000000-0000-0000-0000-000000000001"
        assert args[2] == ["n1", "n2"]

    async def test_mark_read_idempotent_second_call(self, async_client):
        """A second identical call reports zero updates but still succeeds."""
        with patch(
            "app.api.notifications_inbox.notification_service.mark_notifications_read",
            new_callable=AsyncMock,
            return_value=0,
        ):
            response = await async_client.post(
                "/api/notifications/mark-read", json={"ids": ["n1", "n2"]}
            )

        assert response.status_code == 200
        assert response.json()["updated"] == 0

    async def test_mark_read_requires_ids(self, async_client):
        """Missing ids body fails validation."""
        response = await async_client.post("/api/notifications/mark-read", json={})
        assert response.status_code == 422


@pytest.mark.asyncio
class TestUnreadCount:
    """Tests for GET /api/notifications/unread-count."""

    async def test_unread_count(self, async_client):
        """Returns the unread notification count."""
        with patch(
            "app.api.notifications_inbox.notification_service.count_unread_notifications",
            new_callable=AsyncMock,
            return_value=4,
        ):
            response = await async_client.get("/api/notifications/unread-count")

        assert response.status_code == 200
        assert response.json()["count"] == 4

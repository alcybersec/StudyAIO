"""Tests for Web Push notification service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.push_subscription import PushSubscription
from app.services.push_service import send_push_notification, subscribe, unsubscribe


def _make_push_sub(
    id: str = "sub-001",
    user_id: str = "user-001",
    endpoint: str = "https://push.example.com/send/abc123",
    p256dh: str = "test-p256dh-key",
    auth: str = "test-auth-secret",
) -> MagicMock:
    """Create a mock PushSubscription."""
    sub = MagicMock(spec=PushSubscription)
    sub.id = id
    sub.user_id = user_id
    sub.endpoint = endpoint
    sub.p256dh = p256dh
    sub.auth = auth
    return sub


class TestSubscribe:
    """Tests for subscribe."""

    @pytest.mark.asyncio
    async def test_subscribe_creates_new_subscription(self) -> None:
        """Creates a new PushSubscription when no existing one matches."""
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        # execute returns no existing subscription
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result_mock)

        await subscribe(
            session,
            user_id="user-001",
            endpoint="https://push.example.com/send/abc123",
            p256dh="new-p256dh",
            auth="new-auth",
        )

        session.add.assert_called_once()
        added_obj = session.add.call_args[0][0]
        assert isinstance(added_obj, PushSubscription)
        assert added_obj.user_id == "user-001"
        assert added_obj.endpoint == "https://push.example.com/send/abc123"
        assert added_obj.p256dh == "new-p256dh"
        assert added_obj.auth == "new-auth"
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_subscribe_updates_existing_subscription(self) -> None:
        """Updates keys on an existing subscription for same user+endpoint."""
        session = AsyncMock()
        session.flush = AsyncMock()

        existing = _make_push_sub(
            p256dh="old-p256dh",
            auth="old-auth",
        )
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing
        session.execute = AsyncMock(return_value=result_mock)

        result = await subscribe(
            session,
            user_id="user-001",
            endpoint="https://push.example.com/send/abc123",
            p256dh="new-p256dh",
            auth="new-auth",
        )

        assert result is existing
        assert existing.p256dh == "new-p256dh"
        assert existing.auth == "new-auth"
        session.flush.assert_awaited_once()


class TestUnsubscribe:
    """Tests for unsubscribe."""

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_subscription(self) -> None:
        """Returns True and deletes when subscription exists."""
        session = AsyncMock()

        result_mock = MagicMock()
        result_mock.rowcount = 1
        session.execute = AsyncMock(return_value=result_mock)

        result = await unsubscribe(
            session,
            user_id="user-001",
            endpoint="https://push.example.com/send/abc123",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_unsubscribe_nonexistent_returns_false(self) -> None:
        """Returns False when no matching subscription to delete."""
        session = AsyncMock()

        result_mock = MagicMock()
        result_mock.rowcount = 0
        session.execute = AsyncMock(return_value=result_mock)

        result = await unsubscribe(
            session,
            user_id="user-001",
            endpoint="https://push.example.com/nonexistent",
        )

        assert result is False


class TestSendPushNotification:
    """Tests for send_push_notification."""

    @pytest.mark.asyncio
    async def test_send_push_notification_success(self) -> None:
        """Sends push to all subscriptions and returns sent count."""
        session = AsyncMock()

        sub1 = _make_push_sub(id="sub-001")
        sub2 = _make_push_sub(id="sub-002", endpoint="https://push.example.com/send/def456")

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [sub1, sub2]
        session.execute = AsyncMock(return_value=result_mock)

        mock_webpush = MagicMock()

        with (
            patch("app.services.push_service.settings") as mock_settings,
            patch(
                "app.services.push_service.send_push_notification.__module__",
                create=True,
            ),
        ):
            mock_settings.vapid_private_key.get_secret_value.return_value = "test-private-key"
            mock_settings.vapid_admin_email = "admin@studyaio.local"

            # Patch pywebpush at the import site inside the function
            with patch.dict(
                "sys.modules",
                {
                    "pywebpush": MagicMock(
                        webpush=mock_webpush,
                        WebPushException=Exception,
                    )
                },
            ):
                sent = await send_push_notification(
                    session,
                    user_id="user-001",
                    title="Test Title",
                    body="Test body",
                    url="/dashboard",
                )

        assert sent == 2
        assert mock_webpush.call_count == 2

    @pytest.mark.asyncio
    async def test_send_push_notification_cleans_stale(self) -> None:
        """Cleans up subscriptions that return 410 Gone."""
        session = AsyncMock()

        stale_sub = _make_push_sub(id="sub-stale")

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [stale_sub]
        session.execute = AsyncMock(return_value=result_mock)

        # Create a mock WebPushException with 410 status
        mock_web_push_exception = type("WebPushException", (Exception,), {})
        mock_response = MagicMock()
        mock_response.status_code = 410
        exc_instance = mock_web_push_exception("Gone")
        exc_instance.response = mock_response

        mock_webpush = MagicMock(side_effect=exc_instance)

        with patch("app.services.push_service.settings") as mock_settings:
            mock_settings.vapid_private_key.get_secret_value.return_value = "test-private-key"
            mock_settings.vapid_admin_email = "admin@studyaio.local"

            with patch.dict(
                "sys.modules",
                {
                    "pywebpush": MagicMock(
                        webpush=mock_webpush,
                        WebPushException=mock_web_push_exception,
                    )
                },
            ):
                sent = await send_push_notification(
                    session,
                    user_id="user-001",
                    title="Test",
                    body="Body",
                )

        assert sent == 0
        # Verify the cleanup delete was called (second execute call)
        assert session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_send_push_no_subscriptions(self) -> None:
        """Returns 0 when user has no push subscriptions."""
        session = AsyncMock()

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=result_mock)

        with patch("app.services.push_service.settings") as mock_settings:
            mock_settings.vapid_private_key.get_secret_value.return_value = "test-private-key"

            sent = await send_push_notification(
                session,
                user_id="user-001",
                title="Test",
                body="Body",
            )

        assert sent == 0

    @pytest.mark.asyncio
    async def test_send_push_no_vapid_key_returns_zero(self) -> None:
        """Returns 0 when VAPID private key is not configured."""
        session = AsyncMock()

        with patch("app.services.push_service.settings") as mock_settings:
            mock_settings.vapid_private_key.get_secret_value.return_value = ""

            sent = await send_push_notification(
                session,
                user_id="user-001",
                title="Test",
                body="Body",
            )

        assert sent == 0

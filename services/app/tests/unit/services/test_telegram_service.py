"""Tests for Telegram bot service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import TelegramLinkError
from app.models.telegram_link import TelegramLink
from app.services.telegram_service import (
    generate_link_token,
    get_link,
    handle_telegram_webhook,
    send_telegram_message,
    unlink,
    verify_link,
)


def _make_mock_session(link: TelegramLink | None = None) -> AsyncMock:
    """Create a mock async session."""
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = link
    session.execute.return_value = result_mock
    return session


class TestGenerateLinkToken:
    """Tests for generate_link_token."""

    @pytest.mark.asyncio
    async def test_generate_token_new_user(self) -> None:
        """generate_link_token creates a new TelegramLink for new user."""
        session = _make_mock_session(link=None)
        token = await generate_link_token(session, "user-1")
        assert isinstance(token, str)
        assert len(token) > 20
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_token_existing_user(self) -> None:
        """generate_link_token updates existing link with new token."""
        existing = TelegramLink(
            id="link-1", user_id="user-1", chat_id=12345, verified=True
        )
        session = _make_mock_session(link=existing)
        token = await generate_link_token(session, "user-1")
        assert isinstance(token, str)
        assert existing.link_token == token
        assert existing.verified is False
        assert existing.chat_id is None
        session.add.assert_not_called()


class TestVerifyLink:
    """Tests for verify_link."""

    @pytest.mark.asyncio
    async def test_verify_link_success(self) -> None:
        """verify_link sets chat_id and verified=True."""
        existing = TelegramLink(
            id="link-1", user_id="user-1", link_token="valid-token"
        )
        session = _make_mock_session(link=existing)
        result = await verify_link(session, "valid-token", 99999, "testuser")
        assert result is True
        assert existing.chat_id == 99999
        assert existing.username == "testuser"
        assert existing.verified is True
        assert existing.link_token is None

    @pytest.mark.asyncio
    async def test_verify_link_invalid_token(self) -> None:
        """verify_link raises TelegramLinkError for invalid token."""
        session = _make_mock_session(link=None)
        with pytest.raises(TelegramLinkError, match="Invalid or expired"):
            await verify_link(session, "bad-token", 99999)


class TestUnlink:
    """Tests for unlink."""

    @pytest.mark.asyncio
    async def test_unlink_existing(self) -> None:
        """unlink removes the TelegramLink and returns True."""
        existing = TelegramLink(id="link-1", user_id="user-1")
        session = _make_mock_session(link=existing)
        result = await unlink(session, "user-1")
        assert result is True
        session.delete.assert_called_once_with(existing)

    @pytest.mark.asyncio
    async def test_unlink_nonexistent(self) -> None:
        """unlink returns False if no link exists."""
        session = _make_mock_session(link=None)
        result = await unlink(session, "user-1")
        assert result is False


class TestSendTelegramMessage:
    """Tests for send_telegram_message."""

    @pytest.mark.asyncio
    async def test_send_message_success(self) -> None:
        """send_telegram_message returns True when bot sends successfully."""
        mock_bot_instance = MagicMock()
        mock_bot_instance.send_message = AsyncMock()
        mock_bot_instance.session = MagicMock()
        mock_bot_instance.session.close = AsyncMock()

        with (
            patch("app.services.telegram_service._telegram_configured", return_value=True),
            patch("app.services.telegram_service.settings") as mock_settings,
            patch("aiogram.Bot", return_value=mock_bot_instance),
        ):
            mock_settings.telegram_bot_token.get_secret_value.return_value = "123:abc"
            result = await send_telegram_message(12345, "Hello")
            assert result is True
            mock_bot_instance.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_no_token(self) -> None:
        """send_telegram_message returns False when bot token not configured."""
        with patch("app.services.telegram_service._telegram_configured", return_value=False):
            result = await send_telegram_message(12345, "Hello")
            assert result is False


class TestHandleTelegramWebhook:
    """Tests for handle_telegram_webhook."""

    @pytest.mark.asyncio
    async def test_webhook_start_with_valid_token(self) -> None:
        """handle_telegram_webhook verifies link on /start <token>."""
        existing = TelegramLink(
            id="link-1", user_id="user-1", link_token="mytoken"
        )
        session = _make_mock_session(link=existing)

        update = {
            "message": {
                "text": "/start mytoken",
                "chat": {"id": 12345},
                "from": {"username": "alex"},
            }
        }
        response = await handle_telegram_webhook(session, update)
        assert "linked" in response.lower()
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_webhook_start_with_invalid_token(self) -> None:
        """handle_telegram_webhook returns error for invalid token."""
        session = _make_mock_session(link=None)

        update = {
            "message": {
                "text": "/start badtoken",
                "chat": {"id": 12345},
                "from": {"username": "alex"},
            }
        }
        response = await handle_telegram_webhook(session, update)
        assert "invalid" in response.lower() or "expired" in response.lower()

    @pytest.mark.asyncio
    async def test_webhook_unknown_message(self) -> None:
        """handle_telegram_webhook returns help text for unknown messages."""
        session = _make_mock_session()
        update = {
            "message": {
                "text": "hello",
                "chat": {"id": 12345},
                "from": {"username": "alex"},
            }
        }
        response = await handle_telegram_webhook(session, update)
        assert "/start" in response

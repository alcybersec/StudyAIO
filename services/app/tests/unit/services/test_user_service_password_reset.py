"""Tests for password reset link delivery.

`request_password_reset` only mints the token; `deliver_password_reset` is what
actually gets it to the user. These cover the delivery half.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.user_service import deliver_password_reset


class TestDeliverPasswordReset:
    """Tests for deliver_password_reset()."""

    @pytest.mark.asyncio
    async def test_builds_reset_url_from_app_base_url(self) -> None:
        """The link points at the frontend reset route, carrying the token."""
        with (
            patch("app.services.user_service.settings") as mock_settings,
            patch(
                "app.services.email_service.send_password_reset", new_callable=AsyncMock
            ) as mock_send,
        ):
            mock_settings.app_base_url = "https://study.example.com"
            mock_settings.self_hosted = False
            mock_send.return_value = True

            await deliver_password_reset("user@test.com", "tok123")

            mock_send.assert_awaited_once_with(
                "user@test.com", "https://study.example.com/reset-password?token=tok123"
            )

    @pytest.mark.asyncio
    async def test_strips_trailing_slash_from_base_url(self) -> None:
        """A trailing slash in the setting must not produce a double slash."""
        with (
            patch("app.services.user_service.settings") as mock_settings,
            patch(
                "app.services.email_service.send_password_reset", new_callable=AsyncMock
            ) as mock_send,
        ):
            mock_settings.app_base_url = "https://study.example.com/"
            mock_settings.self_hosted = False
            mock_send.return_value = True

            await deliver_password_reset("user@test.com", "tok123")

            url = mock_send.await_args[0][1]
            assert url == "https://study.example.com/reset-password?token=tok123"

    @pytest.mark.asyncio
    async def test_url_encodes_the_token(self) -> None:
        """Tokens are URL-safe today, but the link must not break if that changes."""
        with (
            patch("app.services.user_service.settings") as mock_settings,
            patch(
                "app.services.email_service.send_password_reset", new_callable=AsyncMock
            ) as mock_send,
        ):
            mock_settings.app_base_url = "https://x.test"
            mock_settings.self_hosted = False
            mock_send.return_value = True

            await deliver_password_reset("user@test.com", "a b&c")

            assert mock_send.await_args[0][1] == "https://x.test/reset-password?token=a+b%26c"

    @pytest.mark.asyncio
    async def test_returns_true_when_sent(self) -> None:
        """A successful send is reported back to the caller."""
        with (
            patch("app.services.user_service.settings") as mock_settings,
            patch(
                "app.services.email_service.send_password_reset", new_callable=AsyncMock
            ) as mock_send,
        ):
            mock_settings.app_base_url = "https://x.test"
            mock_settings.self_hosted = False
            mock_send.return_value = True

            assert await deliver_password_reset("user@test.com", "tok") is True

    @pytest.mark.asyncio
    async def test_send_failure_is_swallowed(self) -> None:
        """A raising SMTP layer must not turn into a 500 for the caller."""
        with (
            patch("app.services.user_service.settings") as mock_settings,
            patch(
                "app.services.email_service.send_password_reset", new_callable=AsyncMock
            ) as mock_send,
        ):
            mock_settings.app_base_url = "https://x.test"
            mock_settings.self_hosted = False
            mock_send.side_effect = RuntimeError("smtp exploded")

            assert await deliver_password_reset("user@test.com", "tok") is False

    @pytest.mark.asyncio
    async def test_logs_link_when_self_hosted_and_undeliverable(self) -> None:
        """Self-hosted with no SMTP: the link goes to the log so the admin can use it."""
        with (
            patch("app.services.user_service.settings") as mock_settings,
            patch("app.services.user_service.logger") as mock_logger,
            patch(
                "app.services.email_service.send_password_reset", new_callable=AsyncMock
            ) as mock_send,
        ):
            mock_settings.app_base_url = "https://x.test"
            mock_settings.self_hosted = True
            mock_send.return_value = False

            await deliver_password_reset("user@test.com", "tok")

            logged = [c for c in mock_logger.info.call_args_list if "reset" in str(c).lower()]
            assert logged, "expected the reset link to be logged in self-hosted mode"
            assert "https://x.test/reset-password?token=tok" in str(logged[0])

    @pytest.mark.asyncio
    async def test_never_logs_link_in_saas_mode(self) -> None:
        """In SaaS the link is a credential — it must never reach the logs."""
        with (
            patch("app.services.user_service.settings") as mock_settings,
            patch("app.services.user_service.logger") as mock_logger,
            patch(
                "app.services.email_service.send_password_reset", new_callable=AsyncMock
            ) as mock_send,
        ):
            mock_settings.app_base_url = "https://x.test"
            mock_settings.self_hosted = False
            mock_send.return_value = False

            await deliver_password_reset("user@test.com", "tok")

            everything_logged = str(mock_logger.mock_calls)
            assert "tok" not in everything_logged
            assert "reset-password?token" not in everything_logged

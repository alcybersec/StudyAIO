"""Tests for email verification link creation and delivery.

`create_email_verification_link` mints the token; `deliver_email_verification`
gets it to the user. These cover the producer half of the flow — the consumer
(`verify_email_token`) existed before any of this did.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.user import User
from app.services.user_service import (
    EMAIL_VERIFICATION_TOKEN_HOURS,
    create_email_verification_link,
    deliver_email_verification,
    verify_email_token,
)


def _make_user(**overrides) -> User:
    """Create a mock User with sensible defaults."""
    defaults = {
        "id": "user-001",
        "email": "test@example.com",
        "email_verified": False,
    }
    defaults.update(overrides)
    user = MagicMock(spec=User)
    for k, v in defaults.items():
        setattr(user, k, v)
    return user


class TestCreateEmailVerificationLink:
    """Tests for create_email_verification_link()."""

    @pytest.mark.asyncio
    async def test_creates_link_with_email_verification_type(self) -> None:
        """The link must be typed email_verification — verify_email_token only
        consumes links of that type, so any other value is unreachable."""
        session = AsyncMock()
        user = _make_user()

        link = await create_email_verification_link(session, user)

        assert link.link_type == "email_verification"

    @pytest.mark.asyncio
    async def test_link_belongs_to_the_user(self) -> None:
        session = AsyncMock()
        user = _make_user(id="user-42")

        link = await create_email_verification_link(session, user)

        assert link.user_id == "user-42"

    @pytest.mark.asyncio
    async def test_link_expires_in_24_hours(self) -> None:
        """Verification links are intentionally longer-lived than reset links."""
        session = AsyncMock()
        user = _make_user()
        before = datetime.now(UTC)

        link = await create_email_verification_link(session, user)

        assert EMAIL_VERIFICATION_TOKEN_HOURS == 24
        lower = before + timedelta(hours=24)
        upper = datetime.now(UTC) + timedelta(hours=24)
        assert lower <= link.expires_at <= upper

    @pytest.mark.asyncio
    async def test_link_is_fresh_and_unused(self) -> None:
        session = AsyncMock()
        user = _make_user()

        link = await create_email_verification_link(session, user)

        assert link.used_at is None
        assert link.token  # a token was minted, not left empty

    @pytest.mark.asyncio
    async def test_link_is_persisted(self) -> None:
        session = AsyncMock()
        user = _make_user()

        await create_email_verification_link(session, user)

        session.add.assert_called_once()
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_minting_does_not_query_or_touch_existing_links(self) -> None:
        """Resend semantics mirror password reset: a new link does not revoke
        earlier ones — each stays valid until used or expired."""
        session = AsyncMock()
        user = _make_user()

        await create_email_verification_link(session, user)

        session.execute.assert_not_awaited()


class TestDeliverEmailVerification:
    """Tests for deliver_email_verification()."""

    @pytest.mark.asyncio
    async def test_builds_verify_url_from_app_base_url(self) -> None:
        """The link points at the frontend verify route, carrying the token."""
        with (
            patch("app.services.user_service.settings") as mock_settings,
            patch(
                "app.services.email_service.send_email_verification", new_callable=AsyncMock
            ) as mock_send,
        ):
            mock_settings.app_base_url = "https://study.example.com"
            mock_settings.self_hosted = False
            mock_send.return_value = True

            await deliver_email_verification("user@test.com", "tok123")

            mock_send.assert_awaited_once_with(
                "user@test.com", "https://study.example.com/verify-email?token=tok123"
            )

    @pytest.mark.asyncio
    async def test_strips_trailing_slash_from_base_url(self) -> None:
        """A trailing slash in the setting must not produce a double slash."""
        with (
            patch("app.services.user_service.settings") as mock_settings,
            patch(
                "app.services.email_service.send_email_verification", new_callable=AsyncMock
            ) as mock_send,
        ):
            mock_settings.app_base_url = "https://study.example.com/"
            mock_settings.self_hosted = False
            mock_send.return_value = True

            await deliver_email_verification("user@test.com", "tok123")

            assert (
                mock_send.await_args[0][1] == "https://study.example.com/verify-email?token=tok123"
            )

    @pytest.mark.asyncio
    async def test_url_encodes_the_token(self) -> None:
        """Tokens are URL-safe today, but the link must not break if that changes."""
        with (
            patch("app.services.user_service.settings") as mock_settings,
            patch(
                "app.services.email_service.send_email_verification", new_callable=AsyncMock
            ) as mock_send,
        ):
            mock_settings.app_base_url = "https://x.test"
            mock_settings.self_hosted = False
            mock_send.return_value = True

            await deliver_email_verification("user@test.com", "a b&c")

            assert mock_send.await_args[0][1] == "https://x.test/verify-email?token=a+b%26c"

    @pytest.mark.asyncio
    async def test_returns_true_when_sent(self) -> None:
        with (
            patch("app.services.user_service.settings") as mock_settings,
            patch(
                "app.services.email_service.send_email_verification", new_callable=AsyncMock
            ) as mock_send,
        ):
            mock_settings.app_base_url = "https://x.test"
            mock_settings.self_hosted = False
            mock_send.return_value = True

            assert await deliver_email_verification("user@test.com", "tok") is True

    @pytest.mark.asyncio
    async def test_send_failure_is_swallowed(self) -> None:
        """A raising SMTP layer must not turn into an error for the caller."""
        with (
            patch("app.services.user_service.settings") as mock_settings,
            patch(
                "app.services.email_service.send_email_verification", new_callable=AsyncMock
            ) as mock_send,
        ):
            mock_settings.app_base_url = "https://x.test"
            mock_settings.self_hosted = False
            mock_send.side_effect = RuntimeError("smtp exploded")

            assert await deliver_email_verification("user@test.com", "tok") is False

    @pytest.mark.asyncio
    async def test_logs_link_when_self_hosted_and_undeliverable(self) -> None:
        """Self-hosted with no SMTP: the link goes to the log so the operator can use it."""
        with (
            patch("app.services.user_service.settings") as mock_settings,
            patch("app.services.user_service.logger") as mock_logger,
            patch(
                "app.services.email_service.send_email_verification", new_callable=AsyncMock
            ) as mock_send,
        ):
            mock_settings.app_base_url = "https://x.test"
            mock_settings.self_hosted = True
            mock_send.return_value = False

            await deliver_email_verification("user@test.com", "tok")

            logged = [c for c in mock_logger.info.call_args_list if "verify" in str(c).lower()]
            assert logged, "expected the verification link to be logged in self-hosted mode"
            assert "https://x.test/verify-email?token=tok" in str(logged[0])

    @pytest.mark.asyncio
    async def test_never_logs_link_in_saas_mode(self) -> None:
        """In SaaS the link proves address ownership — it must never reach the logs."""
        with (
            patch("app.services.user_service.settings") as mock_settings,
            patch("app.services.user_service.logger") as mock_logger,
            patch(
                "app.services.email_service.send_email_verification", new_callable=AsyncMock
            ) as mock_send,
        ):
            mock_settings.app_base_url = "https://x.test"
            mock_settings.self_hosted = False
            mock_send.return_value = False

            await deliver_email_verification("user@test.com", "tok")

            everything_logged = str(mock_logger.mock_calls)
            assert "tok" not in everything_logged
            assert "verify-email?token" not in everything_logged


class TestVerificationRoundTrip:
    """Producer output must be consumable by the pre-existing verifier."""

    @pytest.mark.asyncio
    async def test_minted_link_passes_token_verification(self) -> None:
        """A link fresh out of create_email_verification_link, fed through
        verify_email_token, flips the user's email_verified flag."""
        user = _make_user(email_verified=False)
        session = AsyncMock()
        session.add = MagicMock()

        link = await create_email_verification_link(session, user)
        # Simulate the lookup verify_email_token performs
        result_link = MagicMock()
        result_link.scalar_one_or_none.return_value = link
        result_user = MagicMock()
        result_user.scalar_one_or_none.return_value = user
        session.execute = AsyncMock(side_effect=[result_link, result_user])

        await verify_email_token(session, link.token)

        assert link.used_at is not None
        assert user.email_verified is True

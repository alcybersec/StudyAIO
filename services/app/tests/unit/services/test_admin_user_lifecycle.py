"""Unit tests for admin user provisioning and lifecycle.

Covers the guard rails as much as the happy paths: an admin panel that can
delete the last admin, or delete the admin using it, locks everyone out of the
instance with no way back.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import UserExistsError
from app.models.user import User
from app.services import admin_service


def make_user(**overrides) -> User:
    defaults = {
        "id": "u-1",
        "email": "tester@example.com",
        "username": "tester",
        "role": "user",
        "tier": "free",
        "is_active": True,
        "email_verified": False,
    }
    defaults.update(overrides)
    return User(**defaults)


def _no_existing_user(mock_session):
    """session.execute(...).scalar_one_or_none() -> None (nothing taken)."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = result


class TestCreateUser:
    @pytest.mark.asyncio
    async def test_creates_an_account_with_no_password(self, mock_session):
        _no_existing_user(mock_session)
        minted = MagicMock(raw_token="tok-123")

        with patch(
            "app.services.admin_service.user_service.request_password_reset",
            AsyncMock(return_value=minted),
        ):
            user, token = await admin_service.create_user(mock_session, "new@example.com", "newbie")

        assert user.hashed_password is None
        assert token == "tok-123"
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_setup_link_outlives_a_normal_reset(self, mock_session):
        """The admin has to relay it, so an hour is not enough."""
        _no_existing_user(mock_session)
        reset = AsyncMock(return_value=MagicMock(raw_token="t"))

        with patch("app.services.admin_service.user_service.request_password_reset", reset):
            await admin_service.create_user(mock_session, "new@example.com", "newbie")

        assert reset.call_args.kwargs["expires_in_hours"] == 24

    @pytest.mark.asyncio
    async def test_honours_role_and_tier(self, mock_session):
        _no_existing_user(mock_session)
        with patch(
            "app.services.admin_service.user_service.request_password_reset",
            AsyncMock(return_value=MagicMock(raw_token="t")),
        ):
            user, _ = await admin_service.create_user(
                mock_session, "a@example.com", "adminuser", role="admin", tier="pro"
            )
        assert user.role == "admin"
        assert user.tier == "pro"

    @pytest.mark.asyncio
    async def test_new_accounts_start_unverified(self, mock_session):
        _no_existing_user(mock_session)
        with patch(
            "app.services.admin_service.user_service.request_password_reset",
            AsyncMock(return_value=MagicMock(raw_token="t")),
        ):
            user, _ = await admin_service.create_user(mock_session, "a@example.com", "u")
        assert user.email_verified is False
        assert user.is_active is True

    @pytest.mark.asyncio
    async def test_rejects_a_duplicate_email(self, mock_session):
        result = MagicMock()
        result.scalar_one_or_none.return_value = make_user()
        mock_session.execute.return_value = result

        with pytest.raises(UserExistsError):
            await admin_service.create_user(mock_session, "tester@example.com", "someone")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("role", ["superuser", "", "ADMIN"])
    async def test_rejects_an_unknown_role(self, mock_session, role):
        with pytest.raises(ValueError, match="role must be"):
            await admin_service.create_user(mock_session, "a@example.com", "u", role=role)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("tier", ["enterprise", "", "FREE"])
    async def test_rejects_an_unknown_tier(self, mock_session, tier):
        with pytest.raises(ValueError, match="tier must be"):
            await admin_service.create_user(mock_session, "a@example.com", "u", tier=tier)


class TestDeleteUser:
    @pytest.mark.asyncio
    async def test_refuses_to_delete_the_acting_admin(self, mock_session):
        with pytest.raises(ValueError, match="your own account"):
            await admin_service.delete_user(mock_session, "admin-1", acting_admin_id="admin-1")

    @pytest.mark.asyncio
    async def test_refuses_to_delete_the_last_admin(self, mock_session):
        mock_session.get = AsyncMock(return_value=make_user(id="admin-2", role="admin"))

        with patch("app.services.admin_service.count_active_admins", AsyncMock(return_value=0)):
            with pytest.raises(ValueError, match="last active admin"):
                await admin_service.delete_user(mock_session, "admin-2", acting_admin_id="admin-1")

    @pytest.mark.asyncio
    async def test_deletes_a_non_last_admin(self, mock_session):
        mock_session.get = AsyncMock(return_value=make_user(id="admin-2", role="admin"))
        purge = AsyncMock(return_value={"users": 1})

        with (
            patch("app.services.admin_service.count_active_admins", AsyncMock(return_value=1)),
            patch("app.services.admin_service.account_service.delete_user_account", purge),
        ):
            counts = await admin_service.delete_user(
                mock_session, "admin-2", acting_admin_id="admin-1"
            )

        assert counts == {"users": 1}
        purge.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_for_an_unknown_user(self, mock_session):
        mock_session.get = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="User not found"):
            await admin_service.delete_user(mock_session, "nope", acting_admin_id="admin-1")

    @pytest.mark.asyncio
    async def test_delegates_to_the_shared_purge(self, mock_session):
        """Admin deletion must not be a second, diverging implementation."""
        mock_session.get = AsyncMock(return_value=make_user())
        purge = AsyncMock(return_value={"users": 1, "courses": 2})

        with patch("app.services.admin_service.account_service.delete_user_account", purge):
            await admin_service.delete_user(mock_session, "u-1", acting_admin_id="admin-1")

        assert purge.await_args.args[1] == "u-1"


class TestIssuePasswordReset:
    @pytest.mark.asyncio
    async def test_mints_a_token(self, mock_session):
        mock_session.get = AsyncMock(return_value=make_user())
        with patch(
            "app.services.admin_service.user_service.request_password_reset",
            AsyncMock(return_value=MagicMock(raw_token="tok")),
        ):
            user, token = await admin_service.issue_password_reset(mock_session, "u-1")
        assert token == "tok"
        assert user.email == "tester@example.com"

    @pytest.mark.asyncio
    async def test_raises_for_an_unknown_user(self, mock_session):
        mock_session.get = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="User not found"):
            await admin_service.issue_password_reset(mock_session, "nope")


class TestIssueEmailVerification:
    @pytest.mark.asyncio
    async def test_mints_a_token(self, mock_session):
        mock_session.get = AsyncMock(return_value=make_user(email_verified=False))
        with patch(
            "app.services.admin_service.user_service.create_email_verification_link",
            AsyncMock(return_value=MagicMock(raw_token="tok")),
        ):
            _, token = await admin_service.issue_email_verification(mock_session, "u-1")
        assert token == "tok"

    @pytest.mark.asyncio
    async def test_refuses_when_already_verified(self, mock_session):
        mock_session.get = AsyncMock(return_value=make_user(email_verified=True))
        with pytest.raises(ValueError, match="already verified"):
            await admin_service.issue_email_verification(mock_session, "u-1")

    @pytest.mark.asyncio
    async def test_raises_for_an_unknown_user(self, mock_session):
        mock_session.get = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="User not found"):
            await admin_service.issue_email_verification(mock_session, "nope")

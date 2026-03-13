"""Tests for user_service business logic."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import AuthenticationError, AuthorizationError, UserExistsError
from app.models.magic_link import MagicLink
from app.models.user import User
from app.services import user_service


def _make_user(**overrides) -> User:
    """Create a mock User with sensible defaults."""
    defaults = {
        "id": "user-001",
        "email": "test@example.com",
        "username": "testuser",
        "hashed_password": "$argon2id$v=19$m=65536,t=3,p=4$hash",
        "role": "user",
        "tier": "free",
        "is_active": True,
        "email_verified": False,
        "mfa_enabled": False,
        "mfa_secret": None,
        "backup_codes": None,
        "avatar_url": None,
        "last_login_at": None,
    }
    defaults.update(overrides)
    user = MagicMock(spec=User)
    for k, v in defaults.items():
        setattr(user, k, v)
    return user


def _make_magic_link(**overrides) -> MagicLink:
    """Create a mock MagicLink."""
    defaults = {
        "id": "link-001",
        "user_id": "user-001",
        "token": "test-token-abc",
        "link_type": "password_reset",
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
        "used_at": None,
    }
    defaults.update(overrides)
    link = MagicMock(spec=MagicLink)
    for k, v in defaults.items():
        setattr(link, k, v)
    return link


def _mock_session_returning(obj):
    """Create an AsyncMock session whose execute().scalar_one_or_none() returns obj."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = obj
    session.execute.return_value = result
    return session


class TestRegisterUser:
    """User registration."""

    @pytest.mark.asyncio
    async def test_register_creates_user(self):
        session = AsyncMock()
        # Both uniqueness checks return None (no duplicate)
        result_none = MagicMock()
        result_none.scalar_one_or_none.return_value = None
        session.execute.return_value = result_none

        user = await user_service.register_user(
            session, "new@example.com", "newuser", "StrongPass1!"
        )
        assert user.email == "new@example.com"
        assert user.username == "newuser"
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_duplicate_email_raises(self):
        existing = _make_user()
        session = _mock_session_returning(existing)

        with pytest.raises(UserExistsError, match="email"):
            await user_service.register_user(session, "test@example.com", "other", "StrongPass1!")

    @pytest.mark.asyncio
    async def test_register_duplicate_username_raises(self):
        session = AsyncMock()
        # First call (email check) returns None, second (username check) returns user
        existing = _make_user()
        result_none = MagicMock()
        result_none.scalar_one_or_none.return_value = None
        result_user = MagicMock()
        result_user.scalar_one_or_none.return_value = existing
        session.execute.side_effect = [result_none, result_user]

        with pytest.raises(UserExistsError, match="username"):
            await user_service.register_user(session, "new@example.com", "testuser", "StrongPass1!")

    @pytest.mark.asyncio
    async def test_register_short_password_raises(self):
        session = AsyncMock()
        with pytest.raises(ValueError, match="at least 8"):
            await user_service.register_user(session, "new@example.com", "newuser", "short")

    @pytest.mark.asyncio
    async def test_register_password_is_hashed(self):
        session = AsyncMock()
        result_none = MagicMock()
        result_none.scalar_one_or_none.return_value = None
        session.execute.return_value = result_none

        user = await user_service.register_user(
            session, "new@example.com", "newuser", "StrongPass1!"
        )
        assert user.hashed_password.startswith("$argon2id$")
        assert user.hashed_password != "StrongPass1!"


class TestAuthenticateUser:
    """User authentication."""

    @pytest.mark.asyncio
    async def test_authenticate_valid(self):
        from app.core.auth import hash_password

        hashed = hash_password("CorrectPass!")
        user = _make_user(hashed_password=hashed)
        session = _mock_session_returning(user)

        result = await user_service.authenticate_user(session, "test@example.com", "CorrectPass!")
        assert result.id == "user-001"

    @pytest.mark.asyncio
    async def test_authenticate_wrong_password(self):
        from app.core.auth import hash_password

        hashed = hash_password("CorrectPass!")
        user = _make_user(hashed_password=hashed)
        session = _mock_session_returning(user)

        with pytest.raises(AuthenticationError, match="Invalid email or password"):
            await user_service.authenticate_user(session, "test@example.com", "WrongPass!")

    @pytest.mark.asyncio
    async def test_authenticate_unknown_email(self):
        session = _mock_session_returning(None)

        with pytest.raises(AuthenticationError, match="Invalid email or password"):
            await user_service.authenticate_user(session, "nobody@example.com", "AnyPass1!")

    @pytest.mark.asyncio
    async def test_authenticate_inactive_user(self):
        from app.core.auth import hash_password

        hashed = hash_password("CorrectPass!")
        user = _make_user(hashed_password=hashed, is_active=False)
        session = _mock_session_returning(user)

        with pytest.raises(AuthenticationError, match="deactivated"):
            await user_service.authenticate_user(session, "test@example.com", "CorrectPass!")

    @pytest.mark.asyncio
    async def test_authenticate_no_password_set(self):
        user = _make_user(hashed_password=None)
        session = _mock_session_returning(user)

        with pytest.raises(AuthenticationError, match="Invalid email or password"):
            await user_service.authenticate_user(session, "test@example.com", "AnyPass1!")


class TestGetUser:
    """User lookup."""

    @pytest.mark.asyncio
    async def test_get_by_id_found(self):
        user = _make_user()
        session = _mock_session_returning(user)
        result = await user_service.get_user_by_id(session, "user-001")
        assert result.id == "user-001"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self):
        session = _mock_session_returning(None)
        result = await user_service.get_user_by_id(session, "nonexistent")
        assert result is None


class TestUpdateProfile:
    """Profile updates."""

    @pytest.mark.asyncio
    async def test_update_username(self):
        user = _make_user()
        session = AsyncMock()
        # First execute: get_user_by_id, second: username uniqueness
        result_user = MagicMock()
        result_user.scalar_one_or_none.return_value = user
        result_none = MagicMock()
        result_none.scalar_one_or_none.return_value = None
        session.execute.side_effect = [result_user, result_none]

        updated = await user_service.update_profile(session, "user-001", username="newname")
        assert updated.username == "newname"


class TestChangePassword:
    """Password change."""

    @pytest.mark.asyncio
    async def test_change_password_valid(self):
        from app.core.auth import hash_password

        old_hashed = hash_password("OldPass1!")
        user = _make_user(hashed_password=old_hashed)
        session = _mock_session_returning(user)

        await user_service.change_password(session, "user-001", "OldPass1!", "NewPass1!")
        assert user.hashed_password != old_hashed

    @pytest.mark.asyncio
    async def test_change_password_wrong_old(self):
        from app.core.auth import hash_password

        old_hashed = hash_password("OldPass1!")
        user = _make_user(hashed_password=old_hashed)
        session = _mock_session_returning(user)

        with pytest.raises(AuthenticationError, match="Current password"):
            await user_service.change_password(session, "user-001", "WrongOld!", "NewPass1!")


class TestPasswordReset:
    """Password reset flow."""

    @pytest.mark.asyncio
    async def test_request_reset_creates_link(self):
        user = _make_user()
        session = _mock_session_returning(user)

        link = await user_service.request_password_reset(session, "test@example.com")
        assert link is not None
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_reset_unknown_email(self):
        session = _mock_session_returning(None)
        link = await user_service.request_password_reset(session, "nobody@example.com")
        assert link is None

    @pytest.mark.asyncio
    async def test_reset_with_valid_token(self):
        link = _make_magic_link()
        user = _make_user()

        session = AsyncMock()
        result_link = MagicMock()
        result_link.scalar_one_or_none.return_value = link
        result_user = MagicMock()
        result_user.scalar_one_or_none.return_value = user
        session.execute.side_effect = [result_link, result_user]

        await user_service.reset_password_with_token(session, "test-token-abc", "NewSecure1!")
        assert link.used_at is not None

    @pytest.mark.asyncio
    async def test_reset_with_expired_token(self):
        link = _make_magic_link(expires_at=datetime.now(UTC) - timedelta(hours=1))
        session = _mock_session_returning(link)

        with pytest.raises(AuthenticationError, match="expired"):
            await user_service.reset_password_with_token(session, "test-token-abc", "NewSecure1!")

    @pytest.mark.asyncio
    async def test_reset_with_used_token(self):
        link = _make_magic_link(used_at=datetime.now(UTC))
        session = _mock_session_returning(link)

        with pytest.raises(AuthenticationError, match="already used"):
            await user_service.reset_password_with_token(session, "test-token-abc", "NewSecure1!")


class TestMFA:
    """MFA enable/disable."""

    @pytest.mark.asyncio
    async def test_enable_mfa_valid_code(self):
        user = _make_user()
        session = _mock_session_returning(user)

        with patch("app.services.user_service.verify_totp", return_value=True):
            codes = await user_service.enable_mfa(session, "user-001", "123456", "JBSWY3DPEHPK3PXP")
        assert len(codes) == 10
        assert user.mfa_enabled is True
        assert user.mfa_secret == "JBSWY3DPEHPK3PXP"

    @pytest.mark.asyncio
    async def test_enable_mfa_invalid_code(self):
        user = _make_user()
        session = _mock_session_returning(user)

        with (
            patch("app.services.user_service.verify_totp", return_value=False),
            pytest.raises(AuthorizationError, match="Invalid TOTP"),
        ):
            await user_service.enable_mfa(session, "user-001", "000000", "JBSWY3DPEHPK3PXP")


class TestOAuth:
    """OAuth account creation/linking."""

    @pytest.mark.asyncio
    async def test_create_new_user_via_oauth(self):
        session = AsyncMock()
        # OAuth lookup: None, email lookup: None, username check: None
        result_none = MagicMock()
        result_none.scalar_one_or_none.return_value = None
        session.execute.return_value = result_none

        user = await user_service.create_or_link_oauth(
            session, "google", "goog-123", "new@example.com"
        )
        assert user.email == "new@example.com"
        assert user.email_verified is True

    @pytest.mark.asyncio
    async def test_link_existing_user_via_oauth(self):
        existing_user = _make_user()
        session = AsyncMock()
        # OAuth lookup: None, email lookup: existing user
        result_none = MagicMock()
        result_none.scalar_one_or_none.return_value = None
        result_user = MagicMock()
        result_user.scalar_one_or_none.return_value = existing_user
        session.execute.side_effect = [result_none, result_user]

        user = await user_service.create_or_link_oauth(
            session, "github", "gh-456", "test@example.com"
        )
        assert user.id == "user-001"

    @pytest.mark.asyncio
    async def test_oauth_no_email_raises(self):
        session = AsyncMock()
        with pytest.raises(AuthenticationError, match="did not return an email"):
            await user_service.create_or_link_oauth(session, "google", "goog-123", "")

"""Tests for user_service business logic."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import Update

from app.core.auth import hash_magic_link_token
from app.core.exceptions import AuthenticationError, AuthorizationError, UserExistsError
from app.models.magic_link import MagicLink
from app.models.user import User
from app.services import user_service

RAW_TEST_TOKEN = "test-token-abc"


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
    """Create a mock MagicLink whose token_hash matches RAW_TEST_TOKEN."""
    defaults = {
        "id": "link-001",
        "user_id": "user-001",
        "token_hash": hash_magic_link_token(RAW_TEST_TOKEN),
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

        minted = await user_service.request_password_reset(session, "test@example.com")
        assert minted is not None
        session.add.assert_called_once()
        assert session.add.call_args[0][0] is minted.link
        assert minted.link.link_type == "password_reset"
        assert minted.raw_token

    @pytest.mark.asyncio
    async def test_request_reset_unknown_email(self):
        session = _mock_session_returning(None)
        minted = await user_service.request_password_reset(session, "nobody@example.com")
        assert minted is None

    @pytest.mark.asyncio
    async def test_request_reset_persists_only_the_hash(self):
        """The raw token must never appear on the persisted row."""
        user = _make_user()
        session = _mock_session_returning(user)

        minted = await user_service.request_password_reset(session, "test@example.com")

        persisted = session.add.call_args[0][0]
        assert persisted.token_hash == hash_magic_link_token(minted.raw_token)
        assert persisted.token_hash != minted.raw_token
        # No attribute on the ORM object carries the raw token.
        assert not hasattr(persisted, "token")
        assert not hasattr(persisted, "raw_token")

    @pytest.mark.asyncio
    async def test_request_reset_invalidates_previous_links(self):
        """Minting a new reset link marks the user's earlier unused links used."""
        user = _make_user()
        session = _mock_session_returning(user)

        await user_service.request_password_reset(session, "test@example.com")

        update_stmts = [
            call.args[0]
            for call in session.execute.call_args_list
            if isinstance(call.args[0], Update)
        ]
        assert len(update_stmts) == 1
        stmt = update_stmts[0]
        assert stmt.table.name == "magic_links"
        compiled = str(stmt.compile())
        assert "used_at" in compiled
        assert "IS NULL" in compiled  # only unused links are invalidated
        params = stmt.compile().params
        assert "user-001" in params.values()
        assert "password_reset" in params.values()

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

        await user_service.reset_password_with_token(session, RAW_TEST_TOKEN, "NewSecure1!")
        assert link.used_at is not None

    @pytest.mark.asyncio
    async def test_reset_lookup_matches_on_hash_not_raw_token(self):
        """The lookup hashes the presented token; the raw value never hits SQL."""
        link = _make_magic_link()
        user = _make_user()

        session = AsyncMock()
        result_link = MagicMock()
        result_link.scalar_one_or_none.return_value = link
        result_user = MagicMock()
        result_user.scalar_one_or_none.return_value = user
        session.execute.side_effect = [result_link, result_user]

        await user_service.reset_password_with_token(session, RAW_TEST_TOKEN, "NewSecure1!")

        select_stmt = session.execute.call_args_list[0].args[0]
        params = select_stmt.compile().params
        assert hash_magic_link_token(RAW_TEST_TOKEN) in params.values()
        assert RAW_TEST_TOKEN not in params.values()
        assert link.token_hash == hash_magic_link_token(RAW_TEST_TOKEN)

    @pytest.mark.asyncio
    async def test_reset_with_expired_token(self):
        link = _make_magic_link(expires_at=datetime.now(UTC) - timedelta(hours=1))
        session = _mock_session_returning(link)

        with pytest.raises(AuthenticationError, match="expired"):
            await user_service.reset_password_with_token(session, RAW_TEST_TOKEN, "NewSecure1!")

    @pytest.mark.asyncio
    async def test_reset_with_used_token(self):
        link = _make_magic_link(used_at=datetime.now(UTC))
        session = _mock_session_returning(link)

        with pytest.raises(AuthenticationError, match="already used"):
            await user_service.reset_password_with_token(session, RAW_TEST_TOKEN, "NewSecure1!")

    @pytest.mark.asyncio
    async def test_reset_with_unknown_token(self):
        session = _mock_session_returning(None)

        with pytest.raises(AuthenticationError, match="Invalid reset token"):
            await user_service.reset_password_with_token(session, "no-such-token", "NewSecure1!")


class TestVerifyEmail:
    """Email verification via magic link token."""

    @pytest.mark.asyncio
    async def test_verify_email_with_valid_token(self):
        link = _make_magic_link(link_type="email_verification")
        user = _make_user(email_verified=False)

        session = AsyncMock()
        result_link = MagicMock()
        result_link.scalar_one_or_none.return_value = link
        result_user = MagicMock()
        result_user.scalar_one_or_none.return_value = user
        session.execute.side_effect = [result_link, result_user]

        await user_service.verify_email_token(session, RAW_TEST_TOKEN)
        assert user.email_verified is True
        assert link.used_at is not None

    @pytest.mark.asyncio
    async def test_verify_email_lookup_matches_on_hash(self):
        link = _make_magic_link(link_type="email_verification")
        user = _make_user()

        session = AsyncMock()
        result_link = MagicMock()
        result_link.scalar_one_or_none.return_value = link
        result_user = MagicMock()
        result_user.scalar_one_or_none.return_value = user
        session.execute.side_effect = [result_link, result_user]

        await user_service.verify_email_token(session, RAW_TEST_TOKEN)

        select_stmt = session.execute.call_args_list[0].args[0]
        params = select_stmt.compile().params
        assert hash_magic_link_token(RAW_TEST_TOKEN) in params.values()
        assert RAW_TEST_TOKEN not in params.values()

    @pytest.mark.asyncio
    async def test_verify_email_with_unknown_token(self):
        session = _mock_session_returning(None)

        with pytest.raises(AuthenticationError, match="Invalid verification token"):
            await user_service.verify_email_token(session, "no-such-token")

    @pytest.mark.asyncio
    async def test_verify_email_with_used_token(self):
        link = _make_magic_link(link_type="email_verification", used_at=datetime.now(UTC))
        session = _mock_session_returning(link)

        with pytest.raises(AuthenticationError, match="already used"):
            await user_service.verify_email_token(session, RAW_TEST_TOKEN)

    @pytest.mark.asyncio
    async def test_verify_email_with_expired_token(self):
        link = _make_magic_link(
            link_type="email_verification", expires_at=datetime.now(UTC) - timedelta(hours=1)
        )
        session = _mock_session_returning(link)

        with pytest.raises(AuthenticationError, match="expired"):
            await user_service.verify_email_token(session, RAW_TEST_TOKEN)


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

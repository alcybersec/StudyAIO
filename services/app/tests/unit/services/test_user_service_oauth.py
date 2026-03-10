"""Tests for user_service.create_or_link_oauth."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import AuthenticationError
from app.models.oauth_account import OAuthAccount
from app.models.user import User
from app.services import user_service


def _make_user(**overrides) -> User:
    """Create a mock User with sensible defaults."""
    defaults = {
        "id": "user-001",
        "email": "test@example.com",
        "username": "testuser",
        "hashed_password": None,
        "role": "user",
        "tier": "free",
        "is_active": True,
        "email_verified": True,
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


def _make_oauth_account(**overrides) -> OAuthAccount:
    """Create a mock OAuthAccount."""
    defaults = {
        "id": "oauth-001",
        "user_id": "user-001",
        "provider": "google",
        "provider_user_id": "goog-123",
        "access_token": "old-access",
        "refresh_token": "old-refresh",
    }
    defaults.update(overrides)
    obj = MagicMock(spec=OAuthAccount)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


class TestCreateOrLinkOAuth:
    """Tests for create_or_link_oauth service function."""

    @pytest.mark.asyncio
    async def test_no_email_raises(self):
        session = AsyncMock()
        with pytest.raises(AuthenticationError, match="did not return an email"):
            await user_service.create_or_link_oauth(
                session, "google", "goog-123", ""
            )

    @pytest.mark.asyncio
    async def test_existing_oauth_account_updates_tokens(self):
        session = AsyncMock()
        existing_oauth = _make_oauth_account()
        user = _make_user()

        # First execute: find existing OAuth account
        result_oauth = MagicMock()
        result_oauth.scalar_one_or_none.return_value = existing_oauth

        # Second execute: get_user_by_id
        result_user = MagicMock()
        result_user.scalar_one_or_none.return_value = user

        session.execute = AsyncMock(side_effect=[result_oauth, result_user])

        returned = await user_service.create_or_link_oauth(
            session, "google", "goog-123", "test@example.com",
            access_token="new-access", refresh_token="new-refresh",
        )

        assert returned is user
        assert existing_oauth.access_token == "new-access"
        assert existing_oauth.refresh_token == "new-refresh"

    @pytest.mark.asyncio
    async def test_existing_oauth_sets_avatar_if_missing(self):
        session = AsyncMock()
        existing_oauth = _make_oauth_account()
        user = _make_user(avatar_url=None)

        result_oauth = MagicMock()
        result_oauth.scalar_one_or_none.return_value = existing_oauth
        result_user = MagicMock()
        result_user.scalar_one_or_none.return_value = user
        session.execute = AsyncMock(side_effect=[result_oauth, result_user])

        await user_service.create_or_link_oauth(
            session, "google", "goog-123", "test@example.com",
            avatar_url="https://example.com/pic.jpg",
        )

        assert user.avatar_url == "https://example.com/pic.jpg"

    @pytest.mark.asyncio
    async def test_existing_oauth_does_not_overwrite_avatar(self):
        session = AsyncMock()
        existing_oauth = _make_oauth_account()
        user = _make_user(avatar_url="https://example.com/old.jpg")

        result_oauth = MagicMock()
        result_oauth.scalar_one_or_none.return_value = existing_oauth
        result_user = MagicMock()
        result_user.scalar_one_or_none.return_value = user
        session.execute = AsyncMock(side_effect=[result_oauth, result_user])

        await user_service.create_or_link_oauth(
            session, "google", "goog-123", "test@example.com",
            avatar_url="https://example.com/new.jpg",
        )

        assert user.avatar_url == "https://example.com/old.jpg"

    @pytest.mark.asyncio
    async def test_existing_user_by_email_links_oauth(self):
        session = AsyncMock()
        session.add = MagicMock()
        user = _make_user(avatar_url=None)

        # First execute: no existing OAuth account
        result_no_oauth = MagicMock()
        result_no_oauth.scalar_one_or_none.return_value = None

        # Second execute: find user by email
        result_user = MagicMock()
        result_user.scalar_one_or_none.return_value = user

        session.execute = AsyncMock(side_effect=[result_no_oauth, result_user])

        returned = await user_service.create_or_link_oauth(
            session, "github", "gh-456", "test@example.com",
            access_token="tok", avatar_url="https://github.com/pic.jpg",
        )

        assert returned is user
        assert user.avatar_url == "https://github.com/pic.jpg"
        # OAuthAccount was added
        assert session.add.call_count == 1

    @pytest.mark.asyncio
    async def test_new_user_created_from_oauth(self):
        session = AsyncMock()
        session.add = MagicMock()

        # First execute: no existing OAuth account
        result_no_oauth = MagicMock()
        result_no_oauth.scalar_one_or_none.return_value = None

        # Second execute: no user by email
        result_no_user = MagicMock()
        result_no_user.scalar_one_or_none.return_value = None

        # Third execute: username check (not taken)
        result_username_free = MagicMock()
        result_username_free.scalar_one_or_none.return_value = None

        session.execute = AsyncMock(
            side_effect=[result_no_oauth, result_no_user, result_username_free]
        )

        returned = await user_service.create_or_link_oauth(
            session, "google", "goog-789", "newuser@example.com",
            access_token="tok", avatar_url="https://example.com/avatar.png",
        )

        # User was added (flush creates it), then OAuthAccount was added
        assert session.add.call_count == 2
        # Check the User was created with correct data
        added_user = session.add.call_args_list[0][0][0]
        assert added_user.email == "newuser@example.com"
        assert added_user.email_verified is True
        assert added_user.avatar_url == "https://example.com/avatar.png"

    @pytest.mark.asyncio
    async def test_new_user_username_dedup(self):
        session = AsyncMock()
        session.add = MagicMock()

        result_no_oauth = MagicMock()
        result_no_oauth.scalar_one_or_none.return_value = None

        result_no_user = MagicMock()
        result_no_user.scalar_one_or_none.return_value = None

        # Username "newuser" is taken, "newuser1" is free
        result_taken = MagicMock()
        result_taken.scalar_one_or_none.return_value = _make_user(username="newuser")
        result_free = MagicMock()
        result_free.scalar_one_or_none.return_value = None

        session.execute = AsyncMock(
            side_effect=[result_no_oauth, result_no_user, result_taken, result_free]
        )

        await user_service.create_or_link_oauth(
            session, "google", "goog-dup", "newuser@example.com",
        )

        added_user = session.add.call_args_list[0][0][0]
        assert added_user.username == "newuser1"

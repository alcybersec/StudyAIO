"""Tests for user_service.create_or_link_oauth.

Issue #70 changed what this function is allowed to do with the provider's
email. It used to attach the OAuth identity to whatever account already held
that address, and to trust the address without asking whether the provider had
verified it. Both are now gated -- see the tests marked "#70" below, and the
function's own docstring for the reasoning.

No value here is shaped like a real credential: provider tokens are the literal
string "<test-placeholder>".
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import (
    AuthenticationError,
    OAuthAccountLinkRequiredError,
    OAuthEmailUnverifiedError,
)
from app.models.oauth_account import OAuthAccount
from app.models.user import User
from app.services import user_service

# Not a credential. Provider tokens are opaque strings these tests only pass
# through, so a placeholder keeps secret scanners off a file full of
# OAuth-shaped fixtures.
PLACEHOLDER_TOKEN = "<test-placeholder>"


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
            await user_service.create_or_link_oauth(session, "google", "goog-123", "")

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
            session,
            "google",
            "goog-123",
            "test@example.com",
            email_verified=True,
            access_token="new-access",
            refresh_token="new-refresh",
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
            session,
            "google",
            "goog-123",
            "test@example.com",
            email_verified=True,
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
            session,
            "google",
            "goog-123",
            "test@example.com",
            email_verified=True,
            avatar_url="https://example.com/new.jpg",
        )

        assert user.avatar_url == "https://example.com/old.jpg"

    @pytest.mark.asyncio
    async def test_existing_user_by_email_links_oauth(self):
        """#70: this used to hold for *any* account sharing the email.

        The old contract was "find the row with this email and attach the
        identity to it", and this test pinned it without caring what was in the
        row. That is the pre-account-takeover: an attacker who registered
        ``victim@example.com`` with a password of their own collected the
        victim's later Google sign-in inside the attacker's account.

        What survives is the narrow half -- an account with **no password**.
        There is no credential to bypass on one: it is OAuth-only, or waiting
        on an emailed setup link, so its only route in already reduces to
        control of the mailbox, which is what a provider-verified address
        proves. The assertions are therefore unchanged, but the precondition is
        now spelled out rather than left to the fixture's default. The password
        case is the test below.
        """
        session = AsyncMock()
        session.add = MagicMock()
        user = _make_user(avatar_url=None, hashed_password=None)

        # First execute: no existing OAuth account
        result_no_oauth = MagicMock()
        result_no_oauth.scalar_one_or_none.return_value = None

        # Second execute: find user by email
        result_user = MagicMock()
        result_user.scalar_one_or_none.return_value = user

        session.execute = AsyncMock(side_effect=[result_no_oauth, result_user])

        returned = await user_service.create_or_link_oauth(
            session,
            "github",
            "gh-456",
            "test@example.com",
            email_verified=True,
            access_token=PLACEHOLDER_TOKEN,
            avatar_url="https://github.com/pic.jpg",
        )

        assert returned is user
        assert user.avatar_url == "https://github.com/pic.jpg"
        # OAuthAccount was added
        assert session.add.call_count == 1

    @pytest.mark.asyncio
    async def test_existing_password_user_by_email_is_refused(self):
        """#70: the case the test above used to cover, now refused.

        Nothing in an OAuth callback proves the caller knows this account's
        password, so nothing in it may hand over this account's session.
        """
        session = AsyncMock()
        session.add = MagicMock()
        user = _make_user(hashed_password="$argon2id$v=19$m=65536,t=3,p=4$hash")

        result_no_oauth = MagicMock()
        result_no_oauth.scalar_one_or_none.return_value = None
        result_user = MagicMock()
        result_user.scalar_one_or_none.return_value = user
        session.execute = AsyncMock(side_effect=[result_no_oauth, result_user])

        with pytest.raises(OAuthAccountLinkRequiredError, match="already exists"):
            await user_service.create_or_link_oauth(
                session,
                "github",
                "gh-456",
                "test@example.com",
                email_verified=True,
                access_token=PLACEHOLDER_TOKEN,
            )

        # Nothing was written: no OAuthAccount row, and the account untouched.
        # A refusal that linked anyway would be worse than no refusal.
        assert session.add.call_count == 0

    @pytest.mark.asyncio
    async def test_refusal_message_points_at_the_password(self):
        """The user has to be told what to do instead, or they retry forever."""
        session = AsyncMock()
        user = _make_user(hashed_password="$argon2id$v=19$m=65536,t=3,p=4$hash")

        result_no_oauth = MagicMock()
        result_no_oauth.scalar_one_or_none.return_value = None
        result_user = MagicMock()
        result_user.scalar_one_or_none.return_value = user
        session.execute = AsyncMock(side_effect=[result_no_oauth, result_user])

        with pytest.raises(OAuthAccountLinkRequiredError) as exc:
            await user_service.create_or_link_oauth(
                session, "google", "goog-123", "test@example.com", email_verified=True
            )

        assert "password" in str(exc.value).lower()


class TestProviderEmailMustBeVerified:
    """#70: an address the provider will not vouch for decides nothing."""

    @pytest.mark.asyncio
    async def test_unverified_email_refuses_to_create_an_account(self):
        session = AsyncMock()
        session.add = MagicMock()

        result_none = MagicMock()
        result_none.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result_none)

        with pytest.raises(OAuthEmailUnverifiedError, match="not verified"):
            await user_service.create_or_link_oauth(
                session, "google", "goog-123", "newuser@example.com", email_verified=False
            )

        assert session.add.call_count == 0

    @pytest.mark.asyncio
    async def test_unverified_email_refuses_to_link(self):
        session = AsyncMock()
        session.add = MagicMock()
        user = _make_user(hashed_password=None)

        result_no_oauth = MagicMock()
        result_no_oauth.scalar_one_or_none.return_value = None
        result_user = MagicMock()
        result_user.scalar_one_or_none.return_value = user
        session.execute = AsyncMock(side_effect=[result_no_oauth, result_user])

        with pytest.raises(OAuthEmailUnverifiedError):
            await user_service.create_or_link_oauth(
                session, "github", "gh-456", "test@example.com", email_verified=False
            )

        assert session.add.call_count == 0

    @pytest.mark.asyncio
    async def test_default_is_unverified(self):
        """A caller that forgets the flag must fail closed, not link."""
        session = AsyncMock()
        session.add = MagicMock()

        result_none = MagicMock()
        result_none.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result_none)

        with pytest.raises(OAuthEmailUnverifiedError):
            await user_service.create_or_link_oauth(
                session, "google", "goog-123", "newuser@example.com"
            )

    @pytest.mark.asyncio
    async def test_known_identity_signs_in_despite_unverified_email(self):
        """The gate is on email-based decisions, not on re-authentication.

        A returning user is identified by provider + provider_user_id; the
        email decides nothing on that path, so a provider that stops vouching
        for it must not lock them out of an account they already own.
        """
        session = AsyncMock()
        existing_oauth = _make_oauth_account()
        user = _make_user()

        result_oauth = MagicMock()
        result_oauth.scalar_one_or_none.return_value = existing_oauth
        result_user = MagicMock()
        result_user.scalar_one_or_none.return_value = user
        session.execute = AsyncMock(side_effect=[result_oauth, result_user])

        returned = await user_service.create_or_link_oauth(
            session,
            "google",
            "goog-123",
            "test@example.com",
            email_verified=False,
            access_token=PLACEHOLDER_TOKEN,
        )

        assert returned is user

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

        await user_service.create_or_link_oauth(
            session,
            "google",
            "goog-789",
            "newuser@example.com",
            email_verified=True,
            access_token=PLACEHOLDER_TOKEN,
            avatar_url="https://example.com/avatar.png",
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
            session,
            "google",
            "goog-dup",
            "newuser@example.com",
            email_verified=True,
        )

        added_user = session.add.call_args_list[0][0][0]
        assert added_user.username == "newuser1"

"""Tests for admin_service.ensure_admin — the first-admin bootstrap."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.deps import DEFAULT_ADMIN_ID
from app.core.exceptions import UserExistsError
from app.services import admin_service


@pytest.fixture
def mock_session():
    """AsyncMock of AsyncSession."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


def _make_user_model(
    id=DEFAULT_ADMIN_ID,
    email="admin@studyaio.local",
    username="admin",
    role="admin",
    tier="pro",
    is_active=True,
):
    """Create a mock User model object."""
    user = MagicMock()
    user.id = id
    user.email = email
    user.username = username
    user.role = role
    user.tier = tier
    user.is_active = is_active
    user.email_verified = True
    user.created_at = datetime(2026, 1, 1, 10, 0, 0)
    user.updated_at = datetime(2026, 1, 1, 10, 0, 0)
    return user


def _minted(token="raw-token-abc"):
    """Stand in for user_service.MintedMagicLink."""
    link = MagicMock()
    link.raw_token = token
    return link


def _no_clash(session):
    """Make every `session.execute(select(...))` return no row."""
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=result)


@pytest.mark.asyncio
class TestEnsureAdmin:
    """Tests for ensure_admin()."""

    async def test_repoints_the_default_admin_row(self, mock_session):
        """The default admin keeps its id, so the data it owns keeps its owner."""
        existing = _make_user_model()
        mock_session.get = AsyncMock(return_value=existing)
        _no_clash(mock_session)

        with patch.object(
            admin_service.user_service,
            "request_password_reset",
            AsyncMock(return_value=_minted()),
        ):
            user, token = await admin_service.ensure_admin(mock_session, "me@example.com")

        assert user.id == DEFAULT_ADMIN_ID
        assert user.email == "me@example.com"
        assert user.role == "admin"
        assert user.is_active is True
        assert token == "raw-token-abc"
        # ensure_admin only flushes; the caller owns the transaction boundary.
        mock_session.commit.assert_not_called()

    async def test_changing_the_email_clears_verification(self, mock_session):
        """A new address is unproven until its owner follows a link."""
        existing = _make_user_model()
        mock_session.get = AsyncMock(return_value=existing)
        _no_clash(mock_session)

        with patch.object(
            admin_service.user_service,
            "request_password_reset",
            AsyncMock(return_value=_minted()),
        ):
            await admin_service.ensure_admin(mock_session, "me@example.com")

        assert existing.email_verified is False

    async def test_unchanged_email_keeps_verification(self, mock_session):
        """Re-running with the same address must not un-verify it."""
        existing = _make_user_model(email="me@example.com")
        mock_session.get = AsyncMock(return_value=existing)
        _no_clash(mock_session)

        with patch.object(
            admin_service.user_service,
            "request_password_reset",
            AsyncMock(return_value=_minted()),
        ):
            await admin_service.ensure_admin(mock_session, "me@example.com")

        assert existing.email_verified is True

    async def test_rejects_an_email_owned_by_someone_else(self, mock_session):
        """Repointing onto a tester's address would hand over their account."""
        existing = _make_user_model()
        mock_session.get = AsyncMock(return_value=existing)
        other = _make_user_model(id="u-2", email="taken@example.com", role="user")
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=other)
        mock_session.execute = AsyncMock(return_value=result)

        with pytest.raises(UserExistsError):
            await admin_service.ensure_admin(mock_session, "taken@example.com")

    async def test_falls_back_to_any_existing_admin(self, mock_session):
        """A renamed or re-seeded instance may have an admin under another id."""
        mock_session.get = AsyncMock(return_value=None)
        found = _make_user_model(id="u-9", email="old@example.com")
        found_result = MagicMock()
        found_result.scalar_one_or_none = MagicMock(return_value=found)
        empty_result = MagicMock()
        empty_result.scalar_one_or_none = MagicMock(return_value=None)
        # Calls: find-fallback-admin select, email-clash select, then the
        # MagicLink revocation update — its result value is never read.
        mock_session.execute = AsyncMock(side_effect=[found_result, empty_result, MagicMock()])

        with patch.object(
            admin_service.user_service,
            "request_password_reset",
            AsyncMock(return_value=_minted()),
        ):
            user, _ = await admin_service.ensure_admin(mock_session, "me@example.com")

        assert user.id == "u-9"

    async def test_creates_an_admin_when_none_exists(self, mock_session):
        """A fresh database has no admin row at all."""
        mock_session.get = AsyncMock(return_value=None)
        _no_clash(mock_session)
        created = _make_user_model(id="u-new", email="me@example.com")

        with patch.object(
            admin_service,
            "create_user",
            AsyncMock(return_value=(created, "fresh-token")),
        ) as create:
            user, token = await admin_service.ensure_admin(mock_session, "me@example.com", "alex")

        create.assert_awaited_once_with(
            mock_session, "me@example.com", "alex", role="admin", tier="pro"
        )
        assert user.id == "u-new"
        assert token == "fresh-token"

    async def test_creates_an_admin_with_default_username_when_none_given(self, mock_session):
        """No `--username` on a fresh instance falls back to a literal "admin"."""
        mock_session.get = AsyncMock(return_value=None)
        _no_clash(mock_session)
        created = _make_user_model(id="u-new", email="me@example.com")

        with patch.object(
            admin_service,
            "create_user",
            AsyncMock(return_value=(created, "fresh-token")),
        ) as create:
            await admin_service.ensure_admin(mock_session, "me@example.com")

        create.assert_awaited_once_with(
            mock_session, "me@example.com", "admin", role="admin", tier="pro"
        )

    async def test_reactivates_a_deactivated_admin(self, mock_session):
        """A deactivated sole admin is exactly the lockout this recovers from."""
        existing = _make_user_model(is_active=False, role="user")
        mock_session.get = AsyncMock(return_value=existing)
        _no_clash(mock_session)

        with patch.object(
            admin_service.user_service,
            "request_password_reset",
            AsyncMock(return_value=_minted()),
        ):
            await admin_service.ensure_admin(mock_session, "admin@studyaio.local")

        assert existing.is_active is True
        assert existing.role == "admin"

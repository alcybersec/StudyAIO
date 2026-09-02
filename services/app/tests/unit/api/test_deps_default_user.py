"""Tests for get_current_user_or_default dependency in self-hosted vs SaaS mode."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.deps import DEFAULT_ADMIN_ID
from app.core.auth import create_access_token
from app.models.user import User


@pytest.mark.asyncio
class TestGetCurrentUserOrDefault:
    """Tests for the get_current_user_or_default dependency."""

    async def test_self_hosted_returns_default_admin(self, mock_session):
        """In self-hosted mode with no JWT, returns default admin user."""
        # Clear cache
        import app.api.deps
        from app.api.deps import get_current_user_or_default

        app.api.deps._default_user_cache = None

        # Mock the admin user lookup
        admin_user = MagicMock(spec=User)
        admin_user.id = DEFAULT_ADMIN_ID
        admin_user.role = "admin"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = admin_user
        mock_session.execute = AsyncMock(return_value=mock_result)

        request = MagicMock()
        request.cookies = {}  # No JWT cookie

        with patch("app.api.deps.settings") as mock_settings:
            mock_settings.self_hosted = True
            user = await get_current_user_or_default(request, mock_session)

        assert user.id == DEFAULT_ADMIN_ID

        # Clean up cache
        app.api.deps._default_user_cache = None

    async def test_saas_mode_requires_auth(self, mock_session):
        """In SaaS mode with no JWT, raises AuthenticationError."""
        from app.api.deps import get_current_user_or_default
        from app.core.exceptions import AuthenticationError

        request = MagicMock()
        request.cookies = {}  # No JWT cookie

        with patch("app.api.deps.settings") as mock_settings:
            mock_settings.self_hosted = False
            with pytest.raises(AuthenticationError):
                await get_current_user_or_default(request, mock_session)


@pytest.mark.asyncio
class TestSelfHostedSessionRevocation:
    """Self-hosted mode falls back to the default admin — but not for a revoked token.

    The fallback exists for users who never logged in. A token revoked by a
    password reset must be rejected, not quietly swapped for the (admin)
    default identity.
    """

    def _session_returning(self, mock_session, user):
        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        mock_session.execute = AsyncMock(return_value=result)

    async def test_revoked_token_is_rejected(self, mock_session, make_user):
        """A revoked session must not be downgraded to the default admin."""
        import app.api.deps
        from app.api.deps import get_current_user_or_default
        from app.core.exceptions import SessionRevokedError

        app.api.deps._default_user_cache = None
        user = make_user(id="user-001", tokens_valid_from=datetime.now(UTC))
        self._session_returning(mock_session, user)

        request = MagicMock()
        request.cookies = {"access_token": create_access_token(user.id, user.role, user.tier)}

        with patch("app.api.deps.settings") as mock_settings:
            mock_settings.self_hosted = True
            with pytest.raises(SessionRevokedError):
                await get_current_user_or_default(request, mock_session)

        app.api.deps._default_user_cache = None

    async def test_absent_token_still_falls_back_to_default_admin(self, mock_session):
        """The convenience the fallback exists for is untouched."""
        import app.api.deps
        from app.api.deps import get_current_user_or_default

        app.api.deps._default_user_cache = None
        admin_user = MagicMock(spec=User)
        admin_user.id = DEFAULT_ADMIN_ID
        admin_user.role = "admin"
        self._session_returning(mock_session, admin_user)

        request = MagicMock()
        request.cookies = {}

        with patch("app.api.deps.settings") as mock_settings:
            mock_settings.self_hosted = True
            user = await get_current_user_or_default(request, mock_session)

        assert user.id == DEFAULT_ADMIN_ID
        app.api.deps._default_user_cache = None

    async def test_garbage_token_still_falls_back_to_default_admin(self, mock_session):
        """Only revocation is special-cased; other auth failures still fall back."""
        import app.api.deps
        from app.api.deps import get_current_user_or_default

        app.api.deps._default_user_cache = None
        admin_user = MagicMock(spec=User)
        admin_user.id = DEFAULT_ADMIN_ID
        admin_user.role = "admin"
        self._session_returning(mock_session, admin_user)

        request = MagicMock()
        request.cookies = {"access_token": "not-a-jwt"}

        with patch("app.api.deps.settings") as mock_settings:
            mock_settings.self_hosted = True
            user = await get_current_user_or_default(request, mock_session)

        assert user.id == DEFAULT_ADMIN_ID
        app.api.deps._default_user_cache = None

    async def test_valid_token_wins_over_default_admin(self, mock_session, make_user):
        """A logged-in self-hosted user keeps their own identity."""
        import app.api.deps
        from app.api.deps import get_current_user_or_default

        app.api.deps._default_user_cache = None
        user = make_user(id="user-001")
        self._session_returning(mock_session, user)

        request = MagicMock()
        request.cookies = {"access_token": create_access_token(user.id, user.role, user.tier)}

        with patch("app.api.deps.settings") as mock_settings:
            mock_settings.self_hosted = True
            returned = await get_current_user_or_default(request, mock_session)

        assert returned.id == "user-001"
        app.api.deps._default_user_cache = None

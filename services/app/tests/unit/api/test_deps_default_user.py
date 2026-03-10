"""Tests for get_current_user_or_default dependency in self-hosted vs SaaS mode."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.deps import DEFAULT_ADMIN_ID
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

"""Tests for OAuth redirect and callback API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.auth import hash_password
from app.core.oauth import OAuthUserInfo
from app.models.user import User


def _make_db_user(**overrides) -> User:
    """Create a mock User that looks like it came from the DB."""
    from datetime import datetime

    defaults = {
        "id": "user-oauth-001",
        "email": "oauth@example.com",
        "username": "oauthuser",
        "hashed_password": None,
        "role": "user",
        "tier": "free",
        "is_active": True,
        "email_verified": True,
        "mfa_enabled": False,
        "mfa_secret": None,
        "avatar_url": "https://example.com/avatar.jpg",
        "backup_codes": None,
        "last_login_at": None,
        "created_at": datetime(2026, 1, 1),
        "updated_at": datetime(2026, 1, 1),
    }
    defaults.update(overrides)
    user = MagicMock(spec=User)
    for k, v in defaults.items():
        setattr(user, k, v)
    return user


class TestOAuthRedirect:
    """GET /api/auth/oauth/{provider}"""

    @pytest.mark.asyncio
    async def test_redirect_invalid_provider_returns_400(self, async_client):
        response = await async_client.get(
            "/api/auth/oauth/invalid", follow_redirects=False
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_redirect_google_returns_302(self, async_client):
        with (
            patch("app.api.auth.store_oauth_state", new_callable=AsyncMock),
            patch("app.api.auth.build_authorize_url", return_value="https://accounts.google.com/o/oauth2/v2/auth?test=1"),
            patch("app.config.settings.google_client_id", "test-client-id"),
        ):
            response = await async_client.get(
                "/api/auth/oauth/google", follow_redirects=False
            )
        assert response.status_code == 302
        assert "accounts.google.com" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_redirect_github_returns_302(self, async_client):
        with (
            patch("app.api.auth.store_oauth_state", new_callable=AsyncMock),
            patch("app.api.auth.build_authorize_url", return_value="https://github.com/login/oauth/authorize?test=1"),
            patch("app.config.settings.github_client_id", "test-client-id"),
        ):
            response = await async_client.get(
                "/api/auth/oauth/github", follow_redirects=False
            )
        assert response.status_code == 302
        assert "github.com" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_redirect_unconfigured_provider_returns_400(self, async_client):
        with (
            patch("app.api.auth.store_oauth_state", new_callable=AsyncMock),
            patch("app.api.auth.build_authorize_url", side_effect=ValueError("Google OAuth not configured")),
        ):
            response = await async_client.get(
                "/api/auth/oauth/google", follow_redirects=False
            )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_redirect_stores_state_in_redis(self, async_client):
        mock_store = AsyncMock()
        with (
            patch("app.api.auth.store_oauth_state", mock_store),
            patch("app.api.auth.build_authorize_url", return_value="https://github.com/login/oauth/authorize?test=1"),
            patch("app.config.settings.github_client_id", "test-client-id"),
        ):
            await async_client.get(
                "/api/auth/oauth/github", follow_redirects=False
            )
        mock_store.assert_called_once()
        # First arg is state (random string), second is provider
        assert mock_store.call_args[0][1] == "github"


class TestOAuthCallback:
    """GET /api/auth/oauth/{provider}/callback"""

    @pytest.mark.asyncio
    async def test_callback_invalid_provider_returns_400(self, async_client):
        response = await async_client.get(
            "/api/auth/oauth/invalid/callback?code=abc&state=xyz",
            follow_redirects=False,
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_callback_provider_error_redirects_to_login(self, async_client):
        response = await async_client.get(
            "/api/auth/oauth/google/callback?error=access_denied",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/login?error=oauth_failed" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_callback_missing_code_redirects_to_login(self, async_client):
        response = await async_client.get(
            "/api/auth/oauth/google/callback?state=xyz",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/login?error=oauth_failed" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_callback_invalid_state_returns_403(self, async_client):
        with patch("app.api.auth.validate_oauth_state", new_callable=AsyncMock, return_value=False):
            response = await async_client.get(
                "/api/auth/oauth/google/callback?code=abc&state=badstate",
                follow_redirects=False,
            )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_callback_no_email_returns_400(self, async_client, mock_session):
        userinfo = OAuthUserInfo(
            provider_user_id="12345",
            email="",
            name="No Email",
            avatar_url=None,
        )
        with (
            patch("app.api.auth.validate_oauth_state", new_callable=AsyncMock, return_value=True),
            patch("app.api.auth.exchange_code_for_token", new_callable=AsyncMock, return_value={"access_token": "tok"}),
            patch("app.api.auth.fetch_userinfo", new_callable=AsyncMock, return_value=userinfo),
        ):
            response = await async_client.get(
                "/api/auth/oauth/google/callback?code=abc&state=validstate",
                follow_redirects=False,
            )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_callback_success_sets_cookies_and_redirects(self, async_client, mock_session):
        user = _make_db_user()
        userinfo = OAuthUserInfo(
            provider_user_id="12345",
            email="oauth@example.com",
            name="OAuth User",
            avatar_url="https://example.com/avatar.jpg",
        )
        with (
            patch("app.api.auth.validate_oauth_state", new_callable=AsyncMock, return_value=True),
            patch("app.api.auth.exchange_code_for_token", new_callable=AsyncMock, return_value={"access_token": "tok"}),
            patch("app.api.auth.fetch_userinfo", new_callable=AsyncMock, return_value=userinfo),
            patch("app.api.auth.user_service.create_or_link_oauth", new_callable=AsyncMock, return_value=user),
        ):
            response = await async_client.get(
                "/api/auth/oauth/google/callback?code=abc&state=validstate",
                follow_redirects=False,
            )
        assert response.status_code == 302
        assert response.headers["location"] == "/"
        assert "access_token" in response.cookies

    @pytest.mark.asyncio
    async def test_callback_exchange_failure_redirects_to_login(self, async_client, mock_session):
        with (
            patch("app.api.auth.validate_oauth_state", new_callable=AsyncMock, return_value=True),
            patch("app.api.auth.exchange_code_for_token", new_callable=AsyncMock, side_effect=Exception("Token exchange failed")),
        ):
            response = await async_client.get(
                "/api/auth/oauth/google/callback?code=abc&state=validstate",
                follow_redirects=False,
            )
        assert response.status_code == 302
        assert "/login?error=oauth_failed" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_callback_passes_avatar_url_to_service(self, async_client, mock_session):
        user = _make_db_user()
        userinfo = OAuthUserInfo(
            provider_user_id="gh-99",
            email="dev@github.com",
            name="GH User",
            avatar_url="https://avatars.githubusercontent.com/u/99",
        )
        mock_create = AsyncMock(return_value=user)
        with (
            patch("app.api.auth.validate_oauth_state", new_callable=AsyncMock, return_value=True),
            patch("app.api.auth.exchange_code_for_token", new_callable=AsyncMock, return_value={"access_token": "tok"}),
            patch("app.api.auth.fetch_userinfo", new_callable=AsyncMock, return_value=userinfo),
            patch("app.api.auth.user_service.create_or_link_oauth", mock_create),
        ):
            await async_client.get(
                "/api/auth/oauth/github/callback?code=abc&state=validstate",
                follow_redirects=False,
            )
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args
        assert call_kwargs.kwargs.get("avatar_url") == "https://avatars.githubusercontent.com/u/99"

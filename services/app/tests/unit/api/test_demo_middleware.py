"""Tests for DemoAccountMiddleware."""

import pytest
from unittest.mock import patch

from app.core.auth import create_access_token


@pytest.fixture
def demo_cookies():
    """Create cookies for a demo user."""
    token = create_access_token("demo-user-id", "demo", "free")
    return {"access_token": token}


@pytest.fixture
def user_cookies():
    """Create cookies for a regular user."""
    token = create_access_token("regular-user-id", "user", "free")
    return {"access_token": token}


class TestDemoMiddleware:
    """Tests for demo account write restrictions."""

    @pytest.mark.asyncio
    @patch("app.core.demo_middleware.settings")
    async def test_get_passes_for_demo_user(self, mock_settings, async_client, demo_cookies):
        """GET requests should pass through for demo users (not blocked by middleware)."""
        mock_settings.demo_enabled = True
        # Use /health endpoint which has no deps — just verifies middleware doesn't block GETs
        response = await async_client.get("/health", cookies=demo_cookies)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @patch("app.core.demo_middleware.settings")
    async def test_post_blocked_for_demo_user(self, mock_settings, async_client, demo_cookies):
        """POST requests should be blocked for demo users."""
        mock_settings.demo_enabled = True
        response = await async_client.post(
            "/api/uploads/single",
            cookies=demo_cookies,
        )
        assert response.status_code == 403
        data = response.json()
        assert "demo" in data["detail"].lower()
        assert data["upgrade_url"] == "/register"

    @pytest.mark.asyncio
    @patch("app.core.demo_middleware.settings")
    async def test_put_blocked_for_demo_user(self, mock_settings, async_client, demo_cookies):
        """PUT requests should be blocked for demo users."""
        mock_settings.demo_enabled = True
        response = await async_client.put(
            "/api/auth/me",
            json={"username": "newname"},
            cookies=demo_cookies,
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    @patch("app.core.demo_middleware.settings")
    async def test_delete_blocked_for_demo_user(self, mock_settings, async_client, demo_cookies):
        """DELETE requests should be blocked for demo users."""
        mock_settings.demo_enabled = True
        response = await async_client.delete(
            "/api/exams/some-id/archive",
            cookies=demo_cookies,
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    @patch("app.core.demo_middleware.settings")
    async def test_post_allowed_for_regular_user(self, mock_settings, async_client, user_cookies):
        """POST requests should pass through for regular users."""
        mock_settings.demo_enabled = True
        response = await async_client.post(
            "/api/uploads/single",
            cookies=user_cookies,
        )
        # Should NOT be 403 — may be 422 or other, but not demo-blocked
        assert response.status_code != 403

    @pytest.mark.asyncio
    @patch("app.core.demo_middleware.settings")
    async def test_auth_logout_allowed_for_demo(self, mock_settings, async_client, demo_cookies):
        """Auth logout path should be allowed for demo users."""
        mock_settings.demo_enabled = True
        response = await async_client.post(
            "/api/auth/logout",
            cookies=demo_cookies,
        )
        assert response.status_code != 403

    @pytest.mark.asyncio
    @patch("app.core.demo_middleware.settings")
    async def test_auth_refresh_allowed_for_demo(self, mock_settings, async_client, demo_cookies):
        """Auth refresh path should be allowed for demo users."""
        mock_settings.demo_enabled = True
        response = await async_client.post(
            "/api/auth/refresh",
            cookies=demo_cookies,
        )
        # Not 403 — may be 401 (no refresh token), but not demo-blocked
        assert response.status_code != 403

    @pytest.mark.asyncio
    @patch("app.core.demo_middleware.settings")
    async def test_disabled_mode_passes_all(self, mock_settings, async_client, demo_cookies):
        """When demo_enabled=False, all requests should pass through."""
        mock_settings.demo_enabled = False
        response = await async_client.post(
            "/api/uploads/single",
            cookies=demo_cookies,
        )
        # Middleware shouldn't block — result is whatever the endpoint returns
        assert response.status_code != 403

    @pytest.mark.asyncio
    @patch("app.core.demo_middleware.settings")
    async def test_no_cookie_passes_through(self, mock_settings, async_client):
        """Requests without cookies should pass through the middleware."""
        mock_settings.demo_enabled = True
        response = await async_client.post("/api/uploads/single")
        # No cookie → middleware passes through, endpoint handles auth
        assert response.status_code != 403

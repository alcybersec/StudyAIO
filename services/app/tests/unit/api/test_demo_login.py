"""Tests for the demo-login endpoint."""

import pytest
from unittest.mock import AsyncMock, patch


class TestDemoLogin:
    """Tests for GET /api/auth/demo-login."""

    @pytest.mark.asyncio
    @patch("app.api.auth.settings")
    @patch("app.api.auth.user_service")
    async def test_demo_login_success(self, mock_user_service, mock_settings, async_client, make_user):
        """When demo is enabled and user exists, should redirect with cookies."""
        mock_settings.demo_enabled = True
        mock_settings.jwt_access_token_expire_minutes = 15
        mock_settings.jwt_refresh_token_expire_days = 7
        demo_user = make_user(
            id="00000000-0000-0000-0000-000000000002",
            email="demo@studyaio.app",
            username="demo",
            role="demo",
            tier="free",
        )
        mock_user_service.get_user_by_id = AsyncMock(return_value=demo_user)

        response = await async_client.get(
            "/api/auth/demo-login",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert response.headers.get("location") == "/"
        # Cookies are in Set-Cookie headers on redirect responses
        set_cookie_headers = response.headers.get_list("set-cookie")
        cookie_str = " ".join(set_cookie_headers)
        assert "access_token" in cookie_str

    @pytest.mark.asyncio
    @patch("app.api.auth.settings")
    async def test_demo_login_disabled(self, mock_settings, async_client):
        """When demo is disabled, should return 404."""
        mock_settings.demo_enabled = False

        response = await async_client.get("/api/auth/demo-login")
        assert response.status_code == 404
        assert "not enabled" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    @patch("app.api.auth.settings")
    @patch("app.api.auth.user_service")
    async def test_demo_login_no_user(self, mock_user_service, mock_settings, async_client):
        """When demo is enabled but user doesn't exist, should return 404."""
        mock_settings.demo_enabled = True
        mock_user_service.get_user_by_id = AsyncMock(return_value=None)

        response = await async_client.get("/api/auth/demo-login")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

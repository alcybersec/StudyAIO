"""Tests for auth API endpoints."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.auth import create_refresh_token, decode_token, hash_password
from app.models.user import User


def _make_db_user(**overrides) -> User:
    """Create a mock User that looks like it came from the DB."""
    from datetime import datetime

    defaults = {
        "id": "user-001",
        "email": "test@example.com",
        "username": "testuser",
        "hashed_password": hash_password("TestPass1!"),
        "role": "user",
        "tier": "free",
        "is_active": True,
        "email_verified": False,
        "mfa_enabled": False,
        "mfa_secret": None,
        "avatar_url": None,
        "backup_codes": None,
        "last_login_at": None,
        "tokens_valid_from": None,
        "created_at": datetime(2026, 1, 1),
        "updated_at": datetime(2026, 1, 1),
    }
    defaults.update(overrides)
    user = MagicMock(spec=User)
    for k, v in defaults.items():
        setattr(user, k, v)
    return user


class TestRegister:
    """POST /api/auth/register"""

    @pytest.mark.asyncio
    async def test_register_success(self, async_client, mock_session):
        result_none = MagicMock()
        result_none.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result_none

        # Patch register_user to return a fully-populated user mock
        user = _make_db_user(email="new@example.com", username="newuser")
        with patch(
            "app.api.auth.user_service.register_user", new_callable=AsyncMock, return_value=user
        ):
            response = await async_client.post(
                "/api/auth/register",
                json={
                    "email": "new@example.com",
                    "username": "newuser",
                    "password": "StrongPass1!",
                },
            )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "new@example.com"
        assert data["username"] == "newuser"
        # Check cookies set
        assert "access_token" in response.cookies
        assert "refresh_token" in response.cookies

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, async_client, mock_session):
        existing = _make_db_user()
        result = MagicMock()
        result.scalar_one_or_none.return_value = existing
        mock_session.execute.return_value = result

        response = await async_client.post(
            "/api/auth/register",
            json={"email": "test@example.com", "username": "other", "password": "StrongPass1!"},
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_register_short_password(self, async_client):
        response = await async_client.post(
            "/api/auth/register",
            json={"email": "new@example.com", "username": "newuser", "password": "short"},
        )
        assert response.status_code == 422  # Pydantic validation


class TestLogin:
    """POST /api/auth/login"""

    @pytest.mark.asyncio
    async def test_login_success(self, async_client, mock_session):
        user = _make_db_user()

        with patch(
            "app.api.auth.user_service.authenticate_user", new_callable=AsyncMock, return_value=user
        ):
            response = await async_client.post(
                "/api/auth/login",
                json={"email": "test@example.com", "password": "TestPass1!"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert "access_token" in response.cookies

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, async_client, mock_session):
        user = _make_db_user()
        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        mock_session.execute.return_value = result

        response = await async_client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "WrongPass!"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_unknown_email(self, async_client, mock_session):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        response = await async_client.post(
            "/api/auth/login",
            json={"email": "nobody@example.com", "password": "AnyPass1!"},
        )
        assert response.status_code == 401


class TestLogout:
    """POST /api/auth/logout"""

    @pytest.mark.asyncio
    async def test_logout_clears_cookies(self, async_client):
        response = await async_client.post("/api/auth/logout")
        assert response.status_code == 200
        # Cookies should be cleared (set-cookie with max-age=0)
        assert response.json()["detail"] == "Logged out"


class TestRefresh:
    """POST /api/auth/refresh"""

    @pytest.mark.asyncio
    async def test_refresh_success(self, async_client, mock_session, auth_cookies, make_user):
        user = make_user()
        cookies, _ = auth_cookies(user=user)
        # Mock the user lookup
        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        mock_session.execute.return_value = result

        response = await async_client.post(
            "/api/auth/refresh",
            cookies=cookies,
        )
        assert response.status_code == 200
        assert "access_token" in response.cookies

    @pytest.mark.asyncio
    async def test_refresh_no_token(self, async_client):
        response = await async_client.post("/api/auth/refresh")
        assert response.status_code == 401


class TestRefreshSessionInvalidation:
    """POST /api/auth/refresh must honor users.tokens_valid_from.

    A stolen refresh token must stop minting access tokens the moment the
    victim resets or changes their password.
    """

    def _session_returning(self, mock_session, user):
        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        mock_session.execute.return_value = result

    @pytest.mark.asyncio
    async def test_refresh_token_minted_before_password_reset_is_rejected(
        self, async_client, mock_session, make_user
    ):
        user = make_user()
        refresh = create_refresh_token(user.id)
        # Reset happened after the refresh token was minted.
        self._session_returning(mock_session, user)
        user.tokens_valid_from = datetime.now(UTC)

        response = await async_client.post("/api/auth/refresh", cookies={"refresh_token": refresh})
        assert response.status_code == 401
        assert "invalidated" in response.json()["detail"]
        # No fresh access token may be handed out.
        assert "access_token" not in response.cookies

    @pytest.mark.asyncio
    async def test_refresh_token_minted_in_reset_second_is_rejected(
        self, async_client, mock_session, make_user
    ):
        """Worst case: refresh token and reset share a second — fail closed."""
        user = make_user()
        refresh = create_refresh_token(user.id)
        self._session_returning(mock_session, user)
        user.tokens_valid_from = datetime.fromtimestamp(decode_token(refresh)["iat"], tz=UTC)

        response = await async_client.post("/api/auth/refresh", cookies={"refresh_token": refresh})
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token_minted_after_password_reset_still_mints_access_token(
        self, async_client, mock_session, make_user
    ):
        user = make_user()
        refresh = create_refresh_token(user.id)
        # Reset happened an hour before this refresh token was minted.
        self._session_returning(mock_session, user)
        user.tokens_valid_from = datetime.now(UTC) - timedelta(hours=1)

        response = await async_client.post("/api/auth/refresh", cookies={"refresh_token": refresh})
        assert response.status_code == 200
        assert "access_token" in response.cookies

    @pytest.mark.asyncio
    async def test_refresh_token_from_change_password_rejects_older_tokens(
        self, async_client, mock_session, make_user
    ):
        """change_password stamps the same cutoff as a reset."""
        user = make_user()
        refresh = create_refresh_token(user.id)
        self._session_returning(mock_session, user)
        user.tokens_valid_from = datetime.now(UTC)

        response = await async_client.post("/api/auth/refresh", cookies={"refresh_token": refresh})
        assert response.status_code == 401


class TestGetMe:
    """GET /api/auth/me"""

    @pytest.mark.asyncio
    async def test_get_me_authenticated(self, async_client, mock_session, auth_cookies, make_user):
        user = make_user()
        cookies, _ = auth_cookies(user=user)
        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        mock_session.execute.return_value = result

        response = await async_client.get("/api/auth/me", cookies=cookies)
        assert response.status_code == 200
        assert response.json()["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_me_unauthenticated(self, async_client):
        response = await async_client.get("/api/auth/me")
        assert response.status_code == 401


class TestCookieSecureFlag:
    """Verify Secure flag propagation from settings."""

    @pytest.mark.asyncio
    async def test_cookie_secure_flag_from_settings(self, async_client, mock_session):
        """Cookies should use settings.cookie_secure value."""
        user = _make_db_user()

        with (
            patch(
                "app.api.auth.user_service.authenticate_user",
                new_callable=AsyncMock,
                return_value=user,
            ),
            patch("app.api.auth.settings.cookie_secure", True),
        ):
            response = await async_client.post(
                "/api/auth/login",
                json={"email": "test@example.com", "password": "TestPass1!"},
            )
        assert response.status_code == 200
        # Check that Set-Cookie headers include Secure
        set_cookie_headers = response.headers.get_list("set-cookie")
        for header in set_cookie_headers:
            assert "Secure" in header

    @pytest.mark.asyncio
    async def test_cookie_not_secure_by_default(self, async_client, mock_session):
        """Cookies should not be Secure when cookie_secure is False."""
        user = _make_db_user()

        with patch(
            "app.api.auth.user_service.authenticate_user", new_callable=AsyncMock, return_value=user
        ):
            response = await async_client.post(
                "/api/auth/login",
                json={"email": "test@example.com", "password": "TestPass1!"},
            )
        assert response.status_code == 200
        set_cookie_headers = response.headers.get_list("set-cookie")
        for header in set_cookie_headers:
            assert "Secure" not in header


class TestForgotPassword:
    """POST /api/auth/forgot-password"""

    @pytest.mark.asyncio
    async def test_forgot_password_always_202(self, async_client, mock_session):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        response = await async_client.post(
            "/api/auth/forgot-password",
            json={"email": "nobody@example.com"},
        )
        # Always 202 regardless of whether user exists (no email leak)
        assert response.status_code == 202

    @pytest.mark.asyncio
    async def test_forgot_password_unknown_email_sends_nothing(self, async_client, mock_session):
        """No user means no token and no email."""
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        with patch(
            "app.api.auth.user_service.deliver_password_reset", new_callable=AsyncMock
        ) as mock_deliver:
            response = await async_client.post(
                "/api/auth/forgot-password",
                json={"email": "nobody@example.com"},
            )

        assert response.status_code == 202
        mock_deliver.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_forgot_password_known_email_delivers_link(self, async_client, mock_session):
        """A real user gets the reset link delivered with their token."""
        link = MagicMock()
        link.token = "reset-token-123"

        with (
            patch(
                "app.api.auth.user_service.request_password_reset", new_callable=AsyncMock
            ) as mock_request,
            patch(
                "app.api.auth.user_service.deliver_password_reset", new_callable=AsyncMock
            ) as mock_deliver,
        ):
            mock_request.return_value = link

            response = await async_client.post(
                "/api/auth/forgot-password",
                json={"email": "real@example.com"},
            )

        assert response.status_code == 202
        mock_deliver.assert_awaited_once_with("real@example.com", "reset-token-123")

    @pytest.mark.asyncio
    async def test_forgot_password_still_202_when_delivery_fails(self, async_client, mock_session):
        """A broken mail server must not leak through as a 500."""
        link = MagicMock()
        link.token = "reset-token-123"

        with (
            patch(
                "app.api.auth.user_service.request_password_reset", new_callable=AsyncMock
            ) as mock_request,
            patch(
                "app.api.auth.user_service.deliver_password_reset", new_callable=AsyncMock
            ) as mock_deliver,
        ):
            mock_request.return_value = link
            mock_deliver.side_effect = RuntimeError("smtp exploded")

            response = await async_client.post(
                "/api/auth/forgot-password",
                json={"email": "real@example.com"},
            )

        assert response.status_code == 202

    @pytest.mark.asyncio
    async def test_forgot_password_delivers_after_commit(self, async_client, mock_session):
        """The token must be committed before the email goes out."""
        link = MagicMock()
        link.token = "reset-token-123"
        order: list[str] = []

        mock_session.commit = AsyncMock(side_effect=lambda: order.append("commit"))

        with (
            patch(
                "app.api.auth.user_service.request_password_reset", new_callable=AsyncMock
            ) as mock_request,
            patch(
                "app.api.auth.user_service.deliver_password_reset", new_callable=AsyncMock
            ) as mock_deliver,
        ):
            mock_request.return_value = link
            mock_deliver.side_effect = lambda *a: order.append("deliver")

            await async_client.post(
                "/api/auth/forgot-password",
                json={"email": "real@example.com"},
            )

        assert order == ["commit", "deliver"]

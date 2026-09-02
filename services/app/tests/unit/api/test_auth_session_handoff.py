"""Tests for endpoints that deliberately end the caller's own session.

``change_password`` and ``disable_mfa`` stamp ``users.tokens_valid_from``,
which revokes every token issued up to that moment — the caller's own access
token included. The endpoints must make that sign-out explicit: clear the
cookies and flag it in the body, so the client redirects with an explanation
instead of tripping over a 401 on its next request.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import AuthenticationError, AuthorizationError

CHANGE_PASSWORD_BODY = {"old_password": "TestPass1!", "new_password": "NewPass1!"}


def cleared_cookies(response) -> set[str]:
    """Return the names of cookies the response tells the browser to drop."""
    return {
        header.split("=", 1)[0]
        for header in response.headers.get_list("set-cookie")
        if "Max-Age=0" in header
    }


def session_returning(mock_session, user) -> None:
    """Point the mocked DB session at ``user`` for get_current_user lookups."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    mock_session.execute.return_value = result


class TestChangePasswordEndsSession:
    """POST /api/auth/change-password"""

    @pytest.mark.asyncio
    async def test_change_password_clears_auth_cookies(
        self, async_client, mock_session, auth_cookies, make_user
    ):
        user = make_user()
        cookies, _ = auth_cookies(user=user)
        session_returning(mock_session, user)

        with patch("app.api.auth.user_service.change_password", new_callable=AsyncMock):
            response = await async_client.post(
                "/api/auth/change-password", json=CHANGE_PASSWORD_BODY, cookies=cookies
            )

        assert response.status_code == 200
        assert cleared_cookies(response) == {"access_token", "refresh_token"}

    @pytest.mark.asyncio
    async def test_change_password_flags_the_sign_out(
        self, async_client, mock_session, auth_cookies, make_user
    ):
        """The client needs a machine-readable signal, not just prose."""
        user = make_user()
        cookies, _ = auth_cookies(user=user)
        session_returning(mock_session, user)

        with patch("app.api.auth.user_service.change_password", new_callable=AsyncMock):
            response = await async_client.post(
                "/api/auth/change-password", json=CHANGE_PASSWORD_BODY, cookies=cookies
            )

        body = response.json()
        assert body["session_ended"] is True
        assert "sign in again" in body["detail"]

    @pytest.mark.asyncio
    async def test_change_password_leaves_caller_token_unusable(
        self, async_client, mock_session, auth_cookies, make_user
    ):
        """Replaying the cookies — what a client ignoring the flag would do —
        must not work."""
        user = make_user()
        cookies, _ = auth_cookies(user=user)
        session_returning(mock_session, user)

        async def stamp_cutoff(*args, **kwargs):
            user.tokens_valid_from = datetime.now(UTC)

        with patch(
            "app.api.auth.user_service.change_password",
            new_callable=AsyncMock,
            side_effect=stamp_cutoff,
        ):
            changed = await async_client.post(
                "/api/auth/change-password", json=CHANGE_PASSWORD_BODY, cookies=cookies
            )
        assert changed.status_code == 200

        replayed = await async_client.get("/api/auth/me", cookies=cookies)
        assert replayed.status_code == 401

    @pytest.mark.asyncio
    async def test_change_password_failure_keeps_the_session(
        self, async_client, mock_session, auth_cookies, make_user
    ):
        """A rejected change must not sign anyone out."""
        user = make_user()
        cookies, _ = auth_cookies(user=user)
        session_returning(mock_session, user)

        with patch(
            "app.api.auth.user_service.change_password",
            new_callable=AsyncMock,
            side_effect=AuthenticationError("Current password is incorrect"),
        ):
            response = await async_client.post(
                "/api/auth/change-password",
                json={"old_password": "WrongPass1!", "new_password": "NewPass1!"},
                cookies=cookies,
            )

        assert response.status_code == 401
        assert cleared_cookies(response) == set()


class TestMFADisableEndsSession:
    """POST /api/auth/mfa/disable — same shape as change-password."""

    @pytest.mark.asyncio
    async def test_mfa_disable_clears_auth_cookies(
        self, async_client, mock_session, auth_cookies, make_user
    ):
        user = make_user(mfa_enabled=True, mfa_secret="SECRET")
        cookies, _ = auth_cookies(user=user)
        session_returning(mock_session, user)

        with patch("app.api.auth.user_service.disable_mfa", new_callable=AsyncMock):
            response = await async_client.post(
                "/api/auth/mfa/disable", json={"totp_code": "123456"}, cookies=cookies
            )

        assert response.status_code == 200
        body = response.json()
        assert body["session_ended"] is True
        assert "sign in again" in body["detail"]
        assert cleared_cookies(response) == {"access_token", "refresh_token"}

    @pytest.mark.asyncio
    async def test_mfa_disable_failure_keeps_the_session(
        self, async_client, mock_session, auth_cookies, make_user
    ):
        user = make_user(mfa_enabled=True, mfa_secret="SECRET")
        cookies, _ = auth_cookies(user=user)
        session_returning(mock_session, user)

        with patch(
            "app.api.auth.user_service.disable_mfa",
            new_callable=AsyncMock,
            side_effect=AuthorizationError("Invalid TOTP code"),
        ):
            response = await async_client.post(
                "/api/auth/mfa/disable", json={"totp_code": "000000"}, cookies=cookies
            )

        assert response.status_code == 403
        assert cleared_cookies(response) == set()

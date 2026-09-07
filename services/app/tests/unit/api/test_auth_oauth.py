"""Tests for OAuth redirect and callback API endpoints.

Issue #70 added three things the callback must do before it mints a session,
each of which is asserted below:

* refuse a `state` that did not come back with the cookie set at redirect time
  (`TestOAuthStateBinding`) -- otherwise an attacker completes consent as
  themselves and lures the victim to the callback URL, and the victim's browser
  gets cookies for the attacker's account;
* refuse to link, or to sign in, on an unverified provider email, and refuse to
  auto-link to a password-backed account (`TestOAuthCallbackRefusals`);
* challenge MFA rather than skip it (`TestOAuthCallbackChallengesMFA`,
  `TestOAuthMFACompletion`).

No literal credential appears here. Provider tokens and MFA secrets are the
string "<test-placeholder>"; the OAuth `state` is a fixed non-secret marker.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.oauth import OAUTH_STATE_COOKIE, OAuthUserInfo
from app.core.security import generate_backup_codes, hash_backup_codes
from app.models.user import User

# Not credentials. Both are opaque strings the tests only pass through.
PLACEHOLDER_TOKEN = "<test-placeholder>"
TEST_SECRET = "<test-placeholder>"

# The state is a random per-flow marker, not a secret to protect here.
TEST_STATE = "state-for-this-flow"
STATE_COOKIE = {OAUTH_STATE_COOKIE: TEST_STATE}


def _callback_url(provider: str, state: str = TEST_STATE) -> str:
    return f"/api/auth/oauth/{provider}/callback?code=abc&state={state}"


def _valid_state():
    """Patch the Redis half of state validation to pass."""
    return patch("app.api.auth.validate_oauth_state", new_callable=AsyncMock, return_value=True)


def _exchange_ok():
    return patch(
        "app.api.auth.exchange_code_for_token",
        new_callable=AsyncMock,
        return_value={"access_token": PLACEHOLDER_TOKEN},
    )


def _userinfo(**overrides) -> OAuthUserInfo:
    defaults = {
        "provider_user_id": "12345",
        "email": "oauth@example.com",
        "name": "OAuth User",
        "avatar_url": "https://example.com/avatar.jpg",
        "email_verified": True,
    }
    defaults.update(overrides)
    return OAuthUserInfo(**defaults)


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
        # Real column, and `is_token_invalidated` compares against it -- a
        # MagicMock here blows up in the pending-token check.
        "tokens_valid_from": None,
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
        response = await async_client.get("/api/auth/oauth/invalid", follow_redirects=False)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_redirect_google_returns_302(self, async_client):
        with (
            patch("app.api.auth.store_oauth_state", new_callable=AsyncMock),
            patch(
                "app.api.auth.build_authorize_url",
                return_value="https://accounts.google.com/o/oauth2/v2/auth?test=1",
            ),
            patch("app.config.settings.google_client_id", "test-client-id"),
        ):
            response = await async_client.get("/api/auth/oauth/google", follow_redirects=False)
        assert response.status_code == 302
        assert "accounts.google.com" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_redirect_github_returns_302(self, async_client):
        with (
            patch("app.api.auth.store_oauth_state", new_callable=AsyncMock),
            patch(
                "app.api.auth.build_authorize_url",
                return_value="https://github.com/login/oauth/authorize?test=1",
            ),
            patch("app.config.settings.github_client_id", "test-client-id"),
        ):
            response = await async_client.get("/api/auth/oauth/github", follow_redirects=False)
        assert response.status_code == 302
        assert "github.com" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_redirect_unconfigured_provider_returns_400(self, async_client):
        with (
            patch("app.api.auth.store_oauth_state", new_callable=AsyncMock),
            patch(
                "app.api.auth.build_authorize_url",
                side_effect=ValueError("Google OAuth not configured"),
            ),
        ):
            response = await async_client.get("/api/auth/oauth/google", follow_redirects=False)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_redirect_stores_state_in_redis(self, async_client):
        mock_store = AsyncMock()
        with (
            patch("app.api.auth.store_oauth_state", mock_store),
            patch(
                "app.api.auth.build_authorize_url",
                return_value="https://github.com/login/oauth/authorize?test=1",
            ),
            patch("app.config.settings.github_client_id", "test-client-id"),
        ):
            await async_client.get("/api/auth/oauth/github", follow_redirects=False)
        mock_store.assert_called_once()
        # First arg is state (random string), second is provider
        assert mock_store.call_args[0][1] == "github"

    @pytest.mark.asyncio
    async def test_redirect_sets_the_state_cookie(self, async_client):
        """#70: the browser has to be handed the other half of the binding.

        Storing the state only in Redis proves we minted it, not that the
        browser at the callback is the one we minted it for.
        """
        mock_store = AsyncMock()
        with (
            patch("app.api.auth.store_oauth_state", mock_store),
            patch(
                "app.api.auth.build_authorize_url",
                return_value="https://github.com/login/oauth/authorize?test=1",
            ),
            patch("app.config.settings.github_client_id", "test-client-id"),
        ):
            response = await async_client.get("/api/auth/oauth/github", follow_redirects=False)

        assert response.cookies[OAUTH_STATE_COOKIE] == mock_store.call_args[0][0]
        cookie_header = next(
            h for h in response.headers.get_list("set-cookie") if h.startswith(OAUTH_STATE_COOKIE)
        )
        assert "HttpOnly" in cookie_header
        # "lax", not "strict": the callback is a cross-site top-level
        # navigation from the provider, which strict would not send it on.
        assert "SameSite=lax" in cookie_header


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
                _callback_url("google"),
                follow_redirects=False,
                cookies=STATE_COOKIE,
            )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_callback_no_email_returns_400(self, async_client, mock_session):
        userinfo = _userinfo(email="", name="No Email", avatar_url=None)
        with (
            patch("app.api.auth.validate_oauth_state", new_callable=AsyncMock, return_value=True),
            patch(
                "app.api.auth.exchange_code_for_token",
                new_callable=AsyncMock,
                return_value={"access_token": "tok"},
            ),
            patch("app.api.auth.fetch_userinfo", new_callable=AsyncMock, return_value=userinfo),
        ):
            response = await async_client.get(
                _callback_url("google"),
                follow_redirects=False,
                cookies=STATE_COOKIE,
            )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_callback_success_sets_cookies_and_redirects(self, async_client, mock_session):
        user = _make_db_user()
        userinfo = _userinfo()
        with (
            patch("app.api.auth.validate_oauth_state", new_callable=AsyncMock, return_value=True),
            patch(
                "app.api.auth.exchange_code_for_token",
                new_callable=AsyncMock,
                return_value={"access_token": "tok"},
            ),
            patch("app.api.auth.fetch_userinfo", new_callable=AsyncMock, return_value=userinfo),
            patch(
                "app.api.auth.user_service.create_or_link_oauth",
                new_callable=AsyncMock,
                return_value=user,
            ),
        ):
            response = await async_client.get(
                _callback_url("google"),
                follow_redirects=False,
                cookies=STATE_COOKIE,
            )
        assert response.status_code == 302
        assert response.headers["location"] == "/"
        assert "access_token" in response.cookies

    @pytest.mark.asyncio
    async def test_callback_exchange_failure_redirects_to_login(self, async_client, mock_session):
        with (
            patch("app.api.auth.validate_oauth_state", new_callable=AsyncMock, return_value=True),
            patch(
                "app.api.auth.exchange_code_for_token",
                new_callable=AsyncMock,
                side_effect=Exception("Token exchange failed"),
            ),
        ):
            response = await async_client.get(
                _callback_url("google"),
                follow_redirects=False,
                cookies=STATE_COOKIE,
            )
        assert response.status_code == 302
        assert "/login?error=oauth_failed" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_callback_passes_avatar_url_to_service(self, async_client, mock_session):
        user = _make_db_user()
        userinfo = _userinfo(
            provider_user_id="gh-99",
            email="dev@github.com",
            name="GH User",
            avatar_url="https://avatars.githubusercontent.com/u/99",
        )
        mock_create = AsyncMock(return_value=user)
        with (
            patch("app.api.auth.validate_oauth_state", new_callable=AsyncMock, return_value=True),
            patch(
                "app.api.auth.exchange_code_for_token",
                new_callable=AsyncMock,
                return_value={"access_token": "tok"},
            ),
            patch("app.api.auth.fetch_userinfo", new_callable=AsyncMock, return_value=userinfo),
            patch("app.api.auth.user_service.create_or_link_oauth", mock_create),
        ):
            await async_client.get(
                _callback_url("github"),
                follow_redirects=False,
                cookies=STATE_COOKIE,
            )
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args
        assert call_kwargs.kwargs.get("avatar_url") == "https://avatars.githubusercontent.com/u/99"


class TestOAuthStateBinding:
    """#70 finding 3: `state` must come back with its cookie.

    Each of these presents a `state` the Redis side accepts -- the exact
    position an attacker who minted a real state is in -- and differs only in
    what the browser carries.
    """

    @pytest.mark.asyncio
    async def test_callback_without_the_state_cookie_is_refused(self, async_client):
        """The login-CSRF case: a valid state in a browser that never began the
        flow."""
        with _valid_state():
            response = await async_client.get(_callback_url("google"), follow_redirects=False)

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_callback_with_a_mismatched_state_cookie_is_refused(self, async_client):
        with _valid_state():
            response = await async_client.get(
                _callback_url("google"),
                follow_redirects=False,
                cookies={OAUTH_STATE_COOKIE: "a-cookie-from-some-other-flow"},
            )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_the_cookie_check_runs_before_redis_is_spent(self, async_client):
        """A state minted for someone else is not this browser's to consume.

        Deleting the Redis entry on its behalf would be doing the attacker's
        cleanup for them, and would turn a repeat attempt into a
        indistinguishable "expired flow".
        """
        validate = AsyncMock(return_value=True)
        with patch("app.api.auth.validate_oauth_state", validate):
            response = await async_client.get(_callback_url("google"), follow_redirects=False)

        assert response.status_code == 403
        validate.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_matching_cookie_still_needs_a_valid_redis_state(self, async_client):
        """The cookie is an added binding, not a replacement: a self-chosen
        state would otherwise pass by simply setting it in both places."""
        with patch("app.api.auth.validate_oauth_state", new_callable=AsyncMock, return_value=False):
            response = await async_client.get(
                _callback_url("google"), follow_redirects=False, cookies=STATE_COOKIE
            )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_successful_callback_clears_the_state_cookie(self, async_client, mock_session):
        """One flow, one state. A cookie left behind is replayable for its full
        ten-minute TTL."""
        user = _make_db_user()
        with (
            _valid_state(),
            _exchange_ok(),
            patch("app.api.auth.fetch_userinfo", new_callable=AsyncMock, return_value=_userinfo()),
            patch(
                "app.api.auth.user_service.create_or_link_oauth",
                new_callable=AsyncMock,
                return_value=user,
            ),
        ):
            response = await async_client.get(
                _callback_url("google"), follow_redirects=False, cookies=STATE_COOKIE
            )

        cleared = [
            h
            for h in response.headers.get_list("set-cookie")
            if h.startswith(OAUTH_STATE_COOKIE) and "Max-Age=0" in h
        ]
        assert cleared


class TestOAuthCallbackRefusals:
    """#70 findings 1 and 2, as the callback surfaces them."""

    async def _callback(self, async_client, service_exc, provider="google"):
        with (
            _valid_state(),
            _exchange_ok(),
            patch("app.api.auth.fetch_userinfo", new_callable=AsyncMock, return_value=_userinfo()),
            patch(
                "app.api.auth.user_service.create_or_link_oauth",
                new_callable=AsyncMock,
                side_effect=service_exc,
            ),
        ):
            return await async_client.get(
                _callback_url(provider), follow_redirects=False, cookies=STATE_COOKIE
            )

    @pytest.mark.asyncio
    async def test_password_account_refusal_sets_no_cookies(self, async_client, mock_session):
        """The takeover in one assertion: no session for an account this flow
        proved nothing about."""
        from app.core.exceptions import OAuthAccountLinkRequiredError

        response = await self._callback(
            async_client, OAuthAccountLinkRequiredError("already exists")
        )

        assert response.status_code == 302
        assert "access_token" not in response.cookies
        assert "refresh_token" not in response.cookies

    @pytest.mark.asyncio
    async def test_password_account_refusal_says_why(self, async_client, mock_session):
        """A bare "oauth_failed" would send the user round the same loop; they
        need to be pointed at their password."""
        from app.core.exceptions import OAuthAccountLinkRequiredError

        response = await self._callback(
            async_client, OAuthAccountLinkRequiredError("already exists")
        )

        assert "error=oauth_account_exists" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_unverified_email_sets_no_cookies(self, async_client, mock_session):
        from app.core.exceptions import OAuthEmailUnverifiedError

        response = await self._callback(async_client, OAuthEmailUnverifiedError("not verified"))

        assert response.status_code == 302
        assert "error=oauth_email_unverified" in response.headers["location"]
        assert "access_token" not in response.cookies

    @pytest.mark.asyncio
    async def test_the_provider_verdict_reaches_the_service(self, async_client, mock_session):
        """The callback must pass the flag through, not decide for itself --
        the service is where the gate lives."""
        user = _make_db_user()
        mock_create = AsyncMock(return_value=user)
        with (
            _valid_state(),
            _exchange_ok(),
            patch(
                "app.api.auth.fetch_userinfo",
                new_callable=AsyncMock,
                return_value=_userinfo(email_verified=False),
            ),
            patch("app.api.auth.user_service.create_or_link_oauth", mock_create),
        ):
            await async_client.get(
                _callback_url("google"), follow_redirects=False, cookies=STATE_COOKIE
            )

        assert mock_create.call_args.kwargs["email_verified"] is False


class TestOAuthCallbackChallengesMFA:
    """#70 finding 2: a second factor is a second factor whichever door the
    first came through."""

    async def _callback_for(self, async_client, user):
        with (
            _valid_state(),
            _exchange_ok(),
            patch("app.api.auth.fetch_userinfo", new_callable=AsyncMock, return_value=_userinfo()),
            patch(
                "app.api.auth.user_service.create_or_link_oauth",
                new_callable=AsyncMock,
                return_value=user,
            ),
        ):
            return await async_client.get(
                _callback_url("google"), follow_redirects=False, cookies=STATE_COOKIE
            )

    @pytest.mark.asyncio
    async def test_mfa_account_gets_no_session_cookies(self, async_client, mock_session):
        """Whoever took over the provider account must still face the factor
        the user believes protects this one."""
        user = _make_db_user(mfa_enabled=True, mfa_secret=TEST_SECRET)

        response = await self._callback_for(async_client, user)

        assert "access_token" not in response.cookies
        assert "refresh_token" not in response.cookies

    @pytest.mark.asyncio
    async def test_mfa_account_is_sent_to_the_challenge(self, async_client, mock_session):
        user = _make_db_user(mfa_enabled=True, mfa_secret=TEST_SECRET)

        response = await self._callback_for(async_client, user)

        assert response.status_code == 302
        assert response.headers["location"] == "/login?mfa=required"
        assert "mfa_pending" in response.cookies

    @pytest.mark.asyncio
    async def test_the_pending_cookie_is_not_a_session(self, async_client, mock_session):
        """It names a user and buys nothing: replayed as an access token it is
        refused, because every other entry point checks the token type."""
        user = _make_db_user(mfa_enabled=True, mfa_secret=TEST_SECRET)

        response = await self._callback_for(async_client, user)
        pending = response.cookies["mfa_pending"]

        me = await async_client.get("/api/auth/me", cookies={"access_token": pending})
        assert me.status_code == 401

    @pytest.mark.asyncio
    async def test_account_without_mfa_still_signs_straight_in(self, async_client, mock_session):
        """The challenge must not become a wall for everyone else."""
        user = _make_db_user(mfa_enabled=False)

        response = await self._callback_for(async_client, user)

        assert response.headers["location"] == "/"
        assert "access_token" in response.cookies


class TestOAuthMFACompletion:
    """POST /api/auth/oauth/mfa -- the second leg of the challenge above."""

    @pytest.fixture
    def throttle(self):
        with (
            patch("app.api.auth.login_throttle.apply_delay", new_callable=AsyncMock) as delay,
            patch("app.api.auth.login_throttle.record_failure", new_callable=AsyncMock) as record,
            patch("app.api.auth.login_throttle.clear", new_callable=AsyncMock) as clear,
        ):
            delay.return_value = 0.0
            yield MagicMock(apply_delay=delay, record_failure=record, clear=clear)

    def _pending_cookie(self, user) -> dict:
        from app.core.auth import create_mfa_pending_token

        return {"mfa_pending": create_mfa_pending_token(user.id)}

    def _session_returns(self, mock_session, user):
        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        mock_session.execute.return_value = result

    @pytest.mark.asyncio
    async def test_correct_totp_completes_the_sign_in(self, async_client, mock_session, throttle):
        user = _make_db_user(mfa_enabled=True, mfa_secret=TEST_SECRET)
        self._session_returns(mock_session, user)

        with patch("app.api.auth.verify_totp", return_value=True):
            response = await async_client.post(
                "/api/auth/oauth/mfa",
                json={"totp_code": "123456"},
                cookies=self._pending_cookie(user),
            )

        assert response.status_code == 200
        assert "access_token" in response.cookies

    @pytest.mark.asyncio
    async def test_a_backup_code_is_accepted_too(self, async_client, mock_session, throttle):
        """An OAuth-only account that lost its authenticator has no password to
        fall back on, so the recovery path has to work here as well."""
        codes = generate_backup_codes(count=3)
        user = _make_db_user(
            mfa_enabled=True,
            mfa_secret=TEST_SECRET,
            backup_codes=json.dumps(hash_backup_codes(codes)),
        )
        self._session_returns(mock_session, user)

        response = await async_client.post(
            "/api/auth/oauth/mfa",
            json={"backup_code": codes[0]},
            cookies=self._pending_cookie(user),
        )

        assert response.status_code == 200
        assert response.json()["backup_codes_remaining"] == 2

    @pytest.mark.asyncio
    async def test_wrong_totp_sets_no_cookies(self, async_client, mock_session, throttle):
        user = _make_db_user(mfa_enabled=True, mfa_secret=TEST_SECRET)
        self._session_returns(mock_session, user)

        with patch("app.api.auth.verify_totp", return_value=False):
            response = await async_client.post(
                "/api/auth/oauth/mfa",
                json={"totp_code": "000000"},
                cookies=self._pending_cookie(user),
            )

        assert response.status_code == 403
        assert "access_token" not in response.cookies

    @pytest.mark.asyncio
    async def test_a_wrong_code_counts_against_the_account_throttle(
        self, async_client, mock_session, throttle
    ):
        """Same reasoning as the password path: an attacker holding a hijacked
        provider account must not get unlimited guesses at the code."""
        user = _make_db_user(mfa_enabled=True, mfa_secret=TEST_SECRET)
        self._session_returns(mock_session, user)

        with patch("app.api.auth.verify_totp", return_value=False):
            await async_client.post(
                "/api/auth/oauth/mfa",
                json={"totp_code": "000000"},
                cookies=self._pending_cookie(user),
            )

        throttle.record_failure.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_code_at_all_is_refused(self, async_client, mock_session, throttle):
        user = _make_db_user(mfa_enabled=True, mfa_secret=TEST_SECRET)
        self._session_returns(mock_session, user)

        response = await async_client.post(
            "/api/auth/oauth/mfa", json={}, cookies=self._pending_cookie(user)
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_without_the_pending_cookie_it_is_refused(
        self, async_client, mock_session, throttle
    ):
        """The cookie *is* the first factor. Without it this endpoint would be
        a way to log in with a TOTP code alone."""
        user = _make_db_user(mfa_enabled=True, mfa_secret=TEST_SECRET)
        self._session_returns(mock_session, user)

        with patch("app.api.auth.verify_totp", return_value=True):
            response = await async_client.post("/api/auth/oauth/mfa", json={"totp_code": "123456"})

        assert response.status_code == 401
        assert "access_token" not in response.cookies

    @pytest.mark.asyncio
    async def test_a_session_cookie_is_not_a_pending_cookie(
        self, async_client, mock_session, throttle, auth_cookies
    ):
        """Token types must not be interchangeable in either direction."""
        user = _make_db_user(mfa_enabled=True, mfa_secret=TEST_SECRET)
        self._session_returns(mock_session, user)
        cookies, _ = auth_cookies(user=user)

        with patch("app.api.auth.verify_totp", return_value=True):
            response = await async_client.post(
                "/api/auth/oauth/mfa",
                json={"totp_code": "123456"},
                cookies={"mfa_pending": cookies["access_token"]},
            )

        assert response.status_code == 401

"""OAuth sign-in end to end: state binding, account creation and linking, MFA, GitHub emails.

Only the two provider round-trips (`exchange_code_for_token`, `fetch_userinfo`)
are replaced. Redis state storage, the state cookie, cookie issuance and the
account decisions in `create_or_link_oauth` all run for real, because the
takeover protections live in exactly those seams.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pyotp
import pytest
from pydantic import SecretStr
from sqlalchemy import select, text

from app.core import oauth as oauth_core
from app.core.auth import ACCESS_TOKEN_COOKIE, MFA_PENDING_COOKIE
from app.core.oauth import OAuthUserInfo
from app.models.oauth_account import OAuthAccount
from app.models.user import User

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture
def providers():
    with (
        patch("app.config.settings.google_client_id", "gid"),
        patch("app.config.settings.google_client_secret", SecretStr("gsecret")),
        patch("app.config.settings.github_client_id", "ghid"),
        patch("app.config.settings.github_client_secret", SecretStr("ghsecret")),
    ):
        yield


def _userinfo(**kw) -> OAuthUserInfo:
    base = {
        "provider_user_id": "g-1",
        "email": "New.Person@Example.com",
        "name": "New Person",
        "avatar_url": "https://img/avatar.png",
        "email_verified": True,
    }
    base.update(kw)
    return OAuthUserInfo(**base)


async def _begin(client, provider="google") -> str:
    """Start a flow like the browser does; returns the state (and leaves the cookie in the jar)."""
    resp = await client.get(f"/api/auth/oauth/{provider}", follow_redirects=False)
    assert resp.status_code == 302
    return client.cookies.get("oauth_state") or resp.cookies["oauth_state"]


async def _callback(client, state, provider="google", userinfo=None, code="auth-code"):
    userinfo = userinfo or _userinfo()
    with (
        patch(
            "app.api.auth.exchange_code_for_token",
            AsyncMock(return_value={"access_token": "at", "refresh_token": "rt"}),
        ),
        patch("app.api.auth.fetch_userinfo", AsyncMock(return_value=userinfo)),
    ):
        return await client.get(
            f"/api/auth/oauth/{provider}/callback",
            params={"code": code, "state": state},
            follow_redirects=False,
        )


class TestStateBinding:
    async def test_state_is_single_use(self, client_factory, providers):
        client = client_factory()
        state = await _begin(client)
        first = await _callback(client, state)
        assert first.status_code == 302 and first.headers["location"] == "/"
        replay = await _callback(client, state)
        assert replay.status_code == 403

    async def test_state_must_come_back_in_the_same_browsers_cookie(
        self, client_factory, providers
    ):
        attacker, victim = client_factory(), client_factory()
        state = await _begin(attacker)
        # The victim's browser holds no (or a different) state cookie.
        no_cookie = await _callback(victim, state)
        assert no_cookie.status_code == 403
        victim.cookies.set("oauth_state", "someone-elses", path="/api/auth/oauth")
        wrong_cookie = await _callback(victim, state)
        assert wrong_cookie.status_code == 403
        # The failed attempts did not burn the legitimate flow.
        assert (await _callback(attacker, state)).status_code == 302

    async def test_state_is_bound_to_its_provider(self, client_factory, providers):
        client = client_factory()
        state = await _begin(client, "google")
        wrong = await _callback(client, state, provider="github")
        assert wrong.status_code == 403

    async def test_provider_error_and_exchange_failure_bounce_to_login(
        self, client_factory, providers
    ):
        client = client_factory()
        state = await _begin(client)
        with (
            patch(
                "app.api.auth.exchange_code_for_token", AsyncMock(side_effect=RuntimeError("boom"))
            ),
        ):
            resp = await client.get(
                "/api/auth/oauth/google/callback",
                params={"code": "c", "state": state},
                follow_redirects=False,
            )
        assert resp.status_code == 302 and "oauth_failed" in resp.headers["location"]
        # The state cookie is cleared on every exit.
        assert any(
            "oauth_state=" in h and "Max-Age=0" in h for h in resp.headers.get_list("set-cookie")
        )

    async def test_missing_email_from_provider_is_a_client_error(self, client_factory, providers):
        client = client_factory()
        state = await _begin(client)
        resp = await _callback(client, state, userinfo=_userinfo(email=""))
        assert resp.status_code == 400


class TestAccountDecisions:
    async def test_first_sign_in_creates_a_verified_normalised_account(
        self, client_factory, providers, db_session
    ):
        client = client_factory()
        state = await _begin(client)
        resp = await _callback(client, state)
        assert resp.status_code == 302 and ACCESS_TOKEN_COOKIE in resp.cookies
        user = (
            await db_session.execute(select(User).where(User.email == "new.person@example.com"))
        ).scalar_one()
        assert user.email_verified is True and user.hashed_password is None
        assert user.username == "new.person" and user.avatar_url == "https://img/avatar.png"
        link = (
            await db_session.execute(select(OAuthAccount).where(OAuthAccount.user_id == user.id))
        ).scalar_one()
        assert (link.provider, link.provider_user_id) == ("google", "g-1")
        # The new session works.
        assert (await client.get("/api/auth/me")).json()["id"] == user.id

    async def test_returning_identity_signs_in_to_the_same_account(
        self, client_factory, providers, db_session
    ):
        for _ in range(2):
            client = client_factory()
            await _callback(client, await _begin(client))
        users = (
            (await db_session.execute(select(User).where(User.email == "new.person@example.com")))
            .scalars()
            .all()
        )
        assert len(users) == 1

    async def test_username_collisions_get_a_numeric_suffix(
        self, client_factory, make_user, providers, db_session
    ):
        await make_user(username="twin")
        client = client_factory()
        info = _userinfo(provider_user_id="g-2", email="twin@example.com")
        await _callback(client, await _begin(client), userinfo=info)
        created = (
            await db_session.execute(select(User).where(User.email == "twin@example.com"))
        ).scalar_one()
        assert created.username == "twin1"

    async def test_unverified_provider_email_is_refused_and_creates_nothing(
        self, client_factory, providers, db_session
    ):
        client = client_factory()
        resp = await _callback(
            client,
            await _begin(client),
            userinfo=_userinfo(email_verified=False, email="nobody@example.com"),
        )
        assert resp.status_code == 302 and "oauth_email_unverified" in resp.headers["location"]
        assert ACCESS_TOKEN_COOKIE not in resp.cookies
        assert (
            await db_session.execute(select(User).where(User.email == "nobody@example.com"))
        ).first() is None

    async def test_password_account_is_never_auto_linked(
        self, client_factory, make_user, providers, db_session
    ):
        """Takeover protection (#70): a verified provider email is not proof of this account."""
        victim = await make_user(email="victim@example.com")
        client = client_factory()
        resp = await _callback(
            client,
            await _begin(client),
            userinfo=_userinfo(provider_user_id="attacker-g", email="victim@example.com"),
        )
        assert resp.status_code == 302 and "oauth_account_exists" in resp.headers["location"]
        assert ACCESS_TOKEN_COOKIE not in resp.cookies
        assert (
            await db_session.execute(select(OAuthAccount).where(OAuthAccount.user_id == victim.id))
        ).first() is None

    async def test_passwordless_existing_account_is_linked(
        self, client_factory, make_user, providers, db_session
    ):
        user = await make_user(email="invited@example.com")
        user.hashed_password = None
        user.email_verified = False
        await db_session.flush()
        client = client_factory()
        resp = await _callback(
            client,
            await _begin(client),
            userinfo=_userinfo(provider_user_id="g-9", email="invited@example.com"),
        )
        assert resp.status_code == 302 and ACCESS_TOKEN_COOKIE in resp.cookies
        link = (
            await db_session.execute(select(OAuthAccount).where(OAuthAccount.user_id == user.id))
        ).scalar_one()
        assert link.provider_user_id == "g-9"


class TestTokensNotStored:
    """SEC-013: the provider's tokens are never persisted; sign-in only needs the identity."""

    async def _tokens(self, db_session, user_id):
        row = (
            await db_session.execute(
                text("SELECT access_token, refresh_token FROM oauth_accounts WHERE user_id = :u"),
                {"u": user_id},
            )
        ).one()
        return row.access_token, row.refresh_token

    async def test_new_link_leaves_tokens_null(self, client_factory, providers, db_session):
        client = client_factory()
        resp = await _callback(client, await _begin(client))
        assert resp.status_code == 302
        user = (
            await db_session.execute(select(User).where(User.email == "new.person@example.com"))
        ).scalar_one()
        assert await self._tokens(db_session, user.id) == (None, None)

    async def test_returning_identity_clears_previously_stored_tokens(
        self, client_factory, providers, db_session
    ):
        client = client_factory()
        await _callback(client, await _begin(client))
        link = (await db_session.execute(select(OAuthAccount))).scalars().all()[-1]
        link.access_token = "legacy-access"
        link.refresh_token = "legacy-refresh"
        await db_session.flush()
        raw = await self._tokens(db_session, link.user_id)
        assert raw[0] is not None and raw[1] is not None  # precondition: row holds tokens

        client = client_factory()
        resp = await _callback(client, await _begin(client))
        assert resp.status_code == 302 and ACCESS_TOKEN_COOKIE in resp.cookies
        assert await self._tokens(db_session, link.user_id) == (None, None)


class TestMfaChallenge:
    async def test_mfa_account_gets_a_pending_token_not_a_session(
        self, client_factory, make_user, providers, db_session
    ):
        user = await make_user(email="mfa@example.com")
        user.hashed_password = None
        secret = pyotp.random_base32()
        user.mfa_enabled, user.mfa_secret = True, secret
        await db_session.flush()

        client = client_factory()
        resp = await _callback(
            client,
            await _begin(client),
            userinfo=_userinfo(provider_user_id="g-mfa", email="mfa@example.com"),
        )
        assert resp.status_code == 302 and resp.headers["location"] == "/login?mfa=required"
        assert ACCESS_TOKEN_COOKIE not in resp.cookies and MFA_PENDING_COOKIE in resp.cookies
        assert (await client.get("/api/auth/me")).status_code == 401  # not signed in yet

        done = await client.post(
            "/api/auth/oauth/mfa", json={"totp_code": pyotp.TOTP(secret).now()}
        )
        assert done.status_code == 200 and done.json()["id"] == user.id
        assert (await client.get("/api/auth/me")).status_code == 200


class TestProviderPlumbing:
    async def test_authorize_url_carries_state_scopes_and_callback(self, providers):
        google = oauth_core.build_authorize_url("google", "STATE")
        assert "state=STATE" in google and "client_id=gid" in google
        assert "access_type" not in google
        github = oauth_core.build_authorize_url("github", "STATE")
        assert "github.com/login/oauth/authorize" in github and "access_type" not in github
        with pytest.raises(ValueError):
            oauth_core.build_authorize_url("myspace", "S")
        with patch("app.config.settings.github_client_id", ""):
            with pytest.raises(ValueError):
                oauth_core.get_provider_config("github")

    async def test_callback_url_uses_the_configured_base(self):
        with patch("app.config.settings.oauth_redirect_base_url", "https://study.example.com"):
            assert (
                oauth_core.build_callback_url("google")
                == "https://study.example.com/api/auth/oauth/google/callback"
            )

    async def test_state_helpers(self):
        state = oauth_core.generate_oauth_state()
        assert len(state) >= 40 and state != oauth_core.generate_oauth_state()
        assert oauth_core.state_matches_cookie(state, state) is True
        assert oauth_core.state_matches_cookie(state, "other") is False
        assert oauth_core.state_matches_cookie("", state) is False
        assert oauth_core.state_matches_cookie(state, None) is False
        await oauth_core.store_oauth_state(state, "google")
        assert await oauth_core.validate_oauth_state(state, "github") is False
        assert await oauth_core.validate_oauth_state(state, "google") is True
        assert await oauth_core.validate_oauth_state(state, "google") is False  # consumed

    @pytest.mark.parametrize(
        ("profile_email", "entries", "expected"),
        [
            # profile email present in the list and verified
            ("a@x.com", [{"email": "A@x.com", "verified": True}], ("a@x.com", True)),
            # profile email listed unverified -> fall back to the primary verified address
            (
                "a@x.com",
                [
                    {"email": "a@x.com", "verified": False},
                    {"email": "p@x.com", "primary": True, "verified": True},
                ],
                ("p@x.com", True),
            ),
            # no profile email -> any verified address
            (
                "",
                [{"email": "v@x.com", "verified": True}, {"email": "u@x.com", "verified": False}],
                ("v@x.com", True),
            ),
            # nothing verified: hand back the profile email, flagged unverified
            ("a@x.com", [{"email": "a@x.com", "verified": False}], ("a@x.com", False)),
            ("", [], ("", False)),
        ],
    )
    async def test_github_email_is_only_trusted_when_github_verified_it(
        self, profile_email, entries, expected
    ):
        with patch.object(oauth_core, "_fetch_github_emails", AsyncMock(return_value=entries)):
            assert (
                await oauth_core._resolve_github_email(SimpleNamespace(), profile_email) == expected
            )

    async def test_github_email_lookup_failure_fails_closed(self):
        with patch.object(
            oauth_core, "_fetch_github_emails", AsyncMock(side_effect=RuntimeError("403"))
        ):
            assert await oauth_core._resolve_github_email(SimpleNamespace(), "a@x.com") == (
                "a@x.com",
                False,
            )

    async def test_fetch_userinfo_normalises_each_provider(self, providers):
        class FakeClient:
            def __init__(self, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, url, headers=None):
                payload = {
                    "https://www.googleapis.com/oauth2/v3/userinfo": {
                        "sub": 123,
                        "email": "g@x.com",
                        "name": "G",
                        "picture": "p",
                        "email_verified": False,
                    },
                    "https://api.github.com/user": {
                        "id": 7,
                        "login": "octo",
                        "email": None,
                        "avatar_url": "a",
                    },
                }[url]
                return SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload)

        with patch.object(oauth_core, "AsyncOAuth2Client", FakeClient):
            google = await oauth_core.fetch_userinfo("google", {"access_token": "t"})
            with patch.object(
                oauth_core,
                "_fetch_github_emails",
                AsyncMock(return_value=[{"email": "o@x.com", "primary": True, "verified": True}]),
            ):
                github = await oauth_core.fetch_userinfo("github", {"access_token": "t"})
        assert (google.provider_user_id, google.email, google.email_verified) == (
            "123",
            "g@x.com",
            False,
        )
        assert (github.provider_user_id, github.name, github.email, github.email_verified) == (
            "7",
            "octo",
            "o@x.com",
            True,
        )

"""Integration tests for /api/auth against a real database and the real cookie chain.

No auth override is used anywhere in this file: requests carry (or lack) a real
signed cookie, so `get_current_user`, the JWT checks and the session-revocation
rule all run. State assertions read the rows back instead of trusting the
response body.
"""

from unittest.mock import AsyncMock, patch

import pyotp
import pytest
from pydantic import SecretStr
from sqlalchemy import select

from app.core.auth import (
    ACCESS_TOKEN_COOKIE,
    REFRESH_TOKEN_COOKIE,
    create_access_token,
    create_mfa_pending_token,
    verify_password,
)
from app.models.magic_link import MagicLink
from app.models.user import User
from app.services import user_service

pytestmark = pytest.mark.asyncio(loop_scope="session")

PASSWORD = "correct-horse-battery"


async def _fetch(db_session, user_id: str) -> User:
    result = await db_session.execute(
        select(User).where(User.id == user_id).execution_options(populate_existing=True)
    )
    return result.scalar_one()


class TestAuthConfig:
    async def test_config_reports_self_hosted_defaults(self, client_factory):
        resp = await client_factory().get("/api/auth/config")
        assert resp.status_code == 200
        body = resp.json()
        assert body["self_hosted"] is True
        # Self-hosted never offers open registration in the UI.
        assert body["registration_enabled"] is False

    async def test_config_saas_open_registration(self, client_factory):
        with patch("app.config.settings.self_hosted", False):
            body = (await client_factory().get("/api/auth/config")).json()
        assert body["registration_enabled"] is True
        assert body["invite_required"] is False

    async def test_config_lists_configured_oauth_providers(self, client_factory):
        with (
            patch("app.config.settings.google_client_id", "gid"),
            patch("app.config.settings.github_client_id", "ghid"),
        ):
            body = (await client_factory().get("/api/auth/config")).json()
        assert body["oauth_providers"] == ["google", "github"]


class TestRegisterAndLogin:
    async def test_register_creates_user_and_sets_cookies(self, client_factory, db_session):
        client = client_factory()
        resp = await client.post(
            "/api/auth/register",
            json={"email": "New.Person@Example.com", "username": "newperson", "password": PASSWORD},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] == "new.person@example.com"  # normalized
        assert ACCESS_TOKEN_COOKIE in resp.cookies
        assert REFRESH_TOKEN_COOKIE in resp.cookies

        user = (
            await db_session.execute(select(User).where(User.username == "newperson"))
        ).scalar_one()
        assert user.role == "user"
        assert user.hashed_password != PASSWORD
        assert verify_password(PASSWORD, user.hashed_password)
        # A verification link was minted for the new account.
        links = (
            (await db_session.execute(select(MagicLink).where(MagicLink.user_id == user.id)))
            .scalars()
            .all()
        )
        assert [link.link_type for link in links] == ["email_verification"]

        # The cookie from registration authenticates /me.
        me = await client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["username"] == "newperson"

    async def test_register_duplicate_email_conflicts(self, client_factory, make_user):
        existing = await make_user(email="dup@example.com")
        resp = await client_factory().post(
            "/api/auth/register",
            json={"email": existing.email, "username": "someoneelse", "password": PASSWORD},
        )
        assert resp.status_code == 409

    async def test_register_closed_mode_rejected(self, client_factory, db_session):
        with patch("app.config.settings.registration_mode", "closed"):
            resp = await client_factory().post(
                "/api/auth/register",
                json={"email": "c@example.com", "username": "closedone", "password": PASSWORD},
            )
        assert resp.status_code in (403, 400)
        found = (
            await db_session.execute(select(User).where(User.username == "closedone"))
        ).scalar_one_or_none()
        assert found is None

    async def test_register_invite_mode_requires_code(self, client_factory, db_session):
        with patch("app.config.settings.registration_mode", "invite"):
            resp = await client_factory().post(
                "/api/auth/register",
                json={"email": "i@example.com", "username": "inviteless", "password": PASSWORD},
            )
        assert resp.status_code >= 400
        found = (
            await db_session.execute(select(User).where(User.username == "inviteless"))
        ).scalar_one_or_none()
        assert found is None

    async def test_login_success_and_wrong_password(self, client_factory, make_user):
        user = await make_user()
        ok = await client_factory().post(
            "/api/auth/login", json={"email": user.email, "password": PASSWORD}
        )
        assert ok.status_code == 200
        assert ok.json()["id"] == user.id
        assert ACCESS_TOKEN_COOKIE in ok.cookies

        bad = await client_factory().post(
            "/api/auth/login", json={"email": user.email, "password": "wrong-password-1"}
        )
        assert bad.status_code == 401
        assert ACCESS_TOKEN_COOKIE not in bad.cookies

    async def test_login_unknown_email_same_status_as_wrong_password(self, client_factory):
        resp = await client_factory().post(
            "/api/auth/login", json={"email": "nobody@example.com", "password": "whatever-123"}
        )
        assert resp.status_code == 401

    async def test_login_deactivated_account_rejected(self, client_factory, make_user):
        user = await make_user(is_active=False)
        resp = await client_factory().post(
            "/api/auth/login", json={"email": user.email, "password": PASSWORD}
        )
        assert resp.status_code == 401

    async def test_logout_clears_cookies(self, client_factory, make_user):
        user = await make_user()
        resp = await client_factory(user).post("/api/auth/logout")
        assert resp.status_code == 200
        cleared = resp.headers.get_list("set-cookie")
        assert any(c.startswith(f"{ACCESS_TOKEN_COOKIE}=") and "Max-Age=0" in c for c in cleared)


class TestSessionAndTokens:
    async def test_me_requires_auth_in_saas_mode(self, client_factory):
        resp = await client_factory().get("/api/auth/me")
        assert resp.status_code == 401

    async def test_garbage_token_rejected(self, client_factory):
        client = client_factory()
        client.cookies.set(ACCESS_TOKEN_COOKIE, "not-a-jwt")
        assert (await client.get("/api/auth/me")).status_code == 401

    async def test_refresh_token_cannot_act_as_access_token(self, client_factory, make_user):
        user = await make_user()
        login = await client_factory().post(
            "/api/auth/login", json={"email": user.email, "password": PASSWORD}
        )
        refresh = login.cookies[REFRESH_TOKEN_COOKIE]
        client = client_factory()
        client.cookies.set(ACCESS_TOKEN_COOKIE, refresh)
        assert (await client.get("/api/auth/me")).status_code == 401

    async def test_refresh_rotates_tokens(self, client_factory, make_user):
        user = await make_user()
        login = await client_factory().post(
            "/api/auth/login", json={"email": user.email, "password": PASSWORD}
        )
        client = client_factory()
        client.cookies.set(REFRESH_TOKEN_COOKIE, login.cookies[REFRESH_TOKEN_COOKIE])
        resp = await client.post("/api/auth/refresh")
        assert resp.status_code == 200
        assert ACCESS_TOKEN_COOKIE in resp.cookies

    async def test_refresh_without_cookie_or_with_access_token(self, client_factory, make_user):
        assert (await client_factory().post("/api/auth/refresh")).status_code == 401
        user = await make_user()
        client = client_factory()
        client.cookies.set(REFRESH_TOKEN_COOKIE, create_access_token(user.id, "user", "free"))
        assert (await client.post("/api/auth/refresh")).status_code == 401

    async def test_deactivated_user_token_rejected(self, client_factory, make_user, db_session):
        user = await make_user()
        client = client_factory(user)
        assert (await client.get("/api/auth/me")).status_code == 200
        user.is_active = False
        await db_session.flush()
        assert (await client.get("/api/auth/me")).status_code == 401

    async def test_update_profile(self, client_factory, make_user, db_session):
        user = await make_user()
        resp = await client_factory(user).put("/api/auth/me", json={"username": "renamed_user_x"})
        assert resp.status_code == 200
        assert (await _fetch(db_session, user.id)).username == "renamed_user_x"

    async def test_update_profile_username_taken(self, client_factory, make_user):
        other = await make_user()
        user = await make_user()
        resp = await client_factory(user).put("/api/auth/me", json={"username": other.username})
        assert resp.status_code == 409


class TestPasswordFlows:
    async def test_change_password_revokes_old_session(self, client_factory, make_user, db_session):
        user = await make_user()
        old_token = create_access_token(user.id, user.role, user.tier)
        client = client_factory(user)
        resp = await client.post(
            "/api/auth/change-password",
            json={"old_password": PASSWORD, "new_password": "brand-new-password-9"},
        )
        assert resp.status_code == 200
        fresh = await _fetch(db_session, user.id)
        assert verify_password("brand-new-password-9", fresh.hashed_password)
        assert fresh.tokens_valid_from is not None

        # The cookie the caller held before the change is now revoked.
        stale = client_factory()
        stale.cookies.set(ACCESS_TOKEN_COOKIE, old_token)
        assert (await stale.get("/api/auth/me")).status_code == 401

    async def test_change_password_wrong_old_password(self, client_factory, make_user, db_session):
        user = await make_user()
        resp = await client_factory(user).post(
            "/api/auth/change-password",
            json={"old_password": "nope-nope-nope", "new_password": "brand-new-password-9"},
        )
        assert resp.status_code == 401
        assert verify_password(PASSWORD, (await _fetch(db_session, user.id)).hashed_password)

    async def test_forgot_and_reset_password_end_to_end(
        self, client_factory, make_user, db_session
    ):
        user = await make_user()
        captured: dict[str, str] = {}

        async def fake_deliver(email: str, token: str) -> bool:
            captured["email"], captured["token"] = email, token
            return True

        with patch.object(user_service, "deliver_password_reset", fake_deliver):
            resp = await client_factory().post(
                "/api/auth/forgot-password", json={"email": user.email}
            )
        assert resp.status_code == 202
        assert captured["email"] == user.email

        # Only the hash of the token is stored.
        link = (
            await db_session.execute(
                select(MagicLink).where(
                    MagicLink.user_id == user.id, MagicLink.link_type == "password_reset"
                )
            )
        ).scalar_one()
        assert link.token_hash != captured["token"]

        reset = await client_factory().post(
            "/api/auth/reset-password",
            json={"token": captured["token"], "new_password": "reset-password-123"},
        )
        assert reset.status_code == 200
        assert verify_password(
            "reset-password-123", (await _fetch(db_session, user.id)).hashed_password
        )

        # Single use.
        again = await client_factory().post(
            "/api/auth/reset-password",
            json={"token": captured["token"], "new_password": "another-password-1"},
        )
        assert again.status_code >= 400

    async def test_forgot_password_unknown_email_looks_identical(self, client_factory):
        resp = await client_factory().post(
            "/api/auth/forgot-password", json={"email": "ghost@example.com"}
        )
        assert resp.status_code == 202

    async def test_reset_password_bad_token(self, client_factory):
        resp = await client_factory().post(
            "/api/auth/reset-password",
            json={"token": "bogus", "new_password": "reset-password-123"},
        )
        assert resp.status_code >= 400


class TestEmailVerification:
    async def test_verify_email_with_minted_token(self, client_factory, make_user, db_session):
        user = await make_user(email_verified=False)
        minted = await user_service.create_email_verification_link(db_session, user)
        resp = await client_factory().post(
            "/api/auth/verify-email", json={"token": minted.raw_token}
        )
        assert resp.status_code == 200
        assert (await _fetch(db_session, user.id)).email_verified is True

    async def test_verify_email_bad_token(self, client_factory):
        resp = await client_factory().post("/api/auth/verify-email", json={"token": "nope"})
        assert resp.status_code >= 400

    async def test_resend_verification(self, client_factory, make_user):
        unverified = await make_user(email_verified=False)
        with patch.object(
            user_service, "deliver_email_verification", AsyncMock(return_value=True)
        ) as deliver:
            resp = await client_factory(unverified).post("/api/auth/resend-verification")
        assert resp.status_code == 202
        deliver.assert_awaited_once()

    async def test_resend_verification_already_verified(self, client_factory, make_user):
        verified = await make_user(email_verified=True)
        resp = await client_factory(verified).post("/api/auth/resend-verification")
        assert resp.status_code == 202
        assert "already" in resp.json()["detail"]


class TestMfa:
    async def _enroll(self, client, db_session, user):
        setup = await client.post("/api/auth/mfa/setup")
        assert setup.status_code == 200
        secret = setup.json()["secret"]
        assert setup.json()["qr_code_base64"]
        verify = await client.post(
            "/api/auth/mfa/verify",
            json={"totp_code": pyotp.TOTP(secret).now(), "secret": secret},
        )
        assert verify.status_code == 200
        return secret, verify.json()["backup_codes"]

    async def test_enroll_login_with_totp_and_backup_code_then_disable(
        self, client_factory, make_user, db_session
    ):
        user = await make_user()
        client = client_factory(user)
        secret, codes = await self._enroll(client, db_session, user)
        assert len(codes) > 0
        stored = await _fetch(db_session, user.id)
        assert stored.mfa_enabled is True
        # Backup codes are stored hashed, never as issued.
        assert not any(code in (stored.backup_codes or "") for code in codes)

        # Re-enrolling over live MFA is refused.
        again = await client.post(
            "/api/auth/mfa/verify",
            json={"totp_code": pyotp.TOTP(secret).now(), "secret": secret},
        )
        assert again.status_code == 400

        anon = client_factory()
        # Password alone is not enough.
        no_code = await anon.post(
            "/api/auth/login", json={"email": user.email, "password": PASSWORD}
        )
        assert no_code.status_code == 403
        wrong = await anon.post(
            "/api/auth/login",
            json={"email": user.email, "password": PASSWORD, "totp_code": "000000"},
        )
        assert wrong.status_code == 403
        good = await anon.post(
            "/api/auth/login",
            json={
                "email": user.email,
                "password": PASSWORD,
                "totp_code": pyotp.TOTP(secret).now(),
            },
        )
        assert good.status_code == 200

        # A backup code works once, then is spent.
        with_backup = await client_factory().post(
            "/api/auth/login",
            json={"email": user.email, "password": PASSWORD, "backup_code": codes[0]},
        )
        assert with_backup.status_code == 200
        assert with_backup.json()["backup_codes_remaining"] == len(codes) - 1
        replay = await client_factory().post(
            "/api/auth/login",
            json={"email": user.email, "password": PASSWORD, "backup_code": codes[0]},
        )
        assert replay.status_code == 403

        # Disable with a valid TOTP.
        disable = await client.post(
            "/api/auth/mfa/disable", json={"totp_code": pyotp.TOTP(secret).now()}
        )
        assert disable.status_code == 200
        after = await _fetch(db_session, user.id)
        assert after.mfa_enabled is False
        assert after.mfa_secret is None
        assert after.backup_codes is None

    async def test_verify_with_wrong_code_does_not_enable(
        self, client_factory, make_user, db_session
    ):
        user = await make_user()
        secret = pyotp.random_base32()
        resp = await client_factory(user).post(
            "/api/auth/mfa/verify", json={"totp_code": "123456", "secret": secret}
        )
        assert resp.status_code == 403
        assert (await _fetch(db_session, user.id)).mfa_enabled is False

    @pytest.mark.xfail(
        strict=True,
        reason="BUG: POST /auth/mfa/disable leaks disable_mfa's ValueError('MFA is not enabled') "
        "as an unhandled 500; /auth/mfa/verify maps the same ValueError to 400",
    )
    async def test_disable_when_not_enabled(self, client_factory, make_user):
        user = await make_user()
        resp = await client_factory(user).post(
            "/api/auth/mfa/disable", json={"totp_code": "123456"}
        )
        assert resp.status_code == 400

    async def test_oauth_mfa_completion(self, client_factory, make_user, db_session):
        user = await make_user()
        secret = pyotp.random_base32()
        user.mfa_secret = secret
        user.mfa_enabled = True
        await db_session.flush()

        client = client_factory()
        # No pending cookie -> refused.
        none = await client.post("/api/auth/oauth/mfa", json={"totp_code": "123456"})
        assert none.status_code == 401

        client.cookies.set("mfa_pending", create_mfa_pending_token(user.id))
        wrong = await client.post("/api/auth/oauth/mfa", json={"totp_code": "000000"})
        assert wrong.status_code == 403
        missing = await client.post("/api/auth/oauth/mfa", json={})
        assert missing.status_code == 403
        ok = await client.post("/api/auth/oauth/mfa", json={"totp_code": pyotp.TOTP(secret).now()})
        assert ok.status_code == 200
        assert ACCESS_TOKEN_COOKIE in ok.cookies

    async def test_oauth_mfa_rejects_wrong_token_type(self, client_factory, make_user):
        user = await make_user()
        client = client_factory()
        client.cookies.set("mfa_pending", create_access_token(user.id, "user", "free"))
        resp = await client.post("/api/auth/oauth/mfa", json={"totp_code": "123456"})
        assert resp.status_code == 401


class TestOAuthRedirects:
    async def test_unknown_provider_rejected(self, client_factory):
        client = client_factory()
        assert (await client.get("/api/auth/oauth/myspace")).status_code == 400
        assert (await client.get("/api/auth/oauth/myspace/callback")).status_code == 400

    async def test_redirect_unconfigured_provider_is_client_error(self, client_factory):
        resp = await client_factory().get("/api/auth/oauth/google", follow_redirects=False)
        assert resp.status_code in (302, 400)

    async def test_redirect_configured_stores_state_and_cookie(self, client_factory):
        with (
            patch("app.config.settings.google_client_id", "gid"),
            patch("app.config.settings.google_client_secret", SecretStr("gsecret")),
        ):
            resp = await client_factory().get("/api/auth/oauth/google", follow_redirects=False)
        assert resp.status_code == 302
        assert "accounts.google.com" in resp.headers["location"]
        assert "oauth_state" in resp.headers.get("set-cookie", "")

    async def test_callback_error_and_missing_params_bounce_to_login(self, client_factory):
        client = client_factory()
        err = await client.get(
            "/api/auth/oauth/google/callback?error=denied", follow_redirects=False
        )
        assert err.status_code == 302 and "oauth_failed" in err.headers["location"]
        missing = await client.get("/api/auth/oauth/google/callback", follow_redirects=False)
        assert missing.status_code == 302

    async def test_callback_state_cookie_mismatch_forbidden(self, client_factory):
        resp = await client_factory().get(
            "/api/auth/oauth/google/callback?code=x&state=forged", follow_redirects=False
        )
        assert resp.status_code == 403


class TestDemoAndAccount:
    async def test_demo_login_disabled(self, client_factory):
        resp = await client_factory().get("/api/auth/demo-login", follow_redirects=False)
        assert resp.status_code == 404

    async def test_demo_login_enabled_without_demo_user(self, client_factory):
        with patch("app.config.settings.demo_enabled", True):
            resp = await client_factory().get("/api/auth/demo-login", follow_redirects=False)
        assert resp.status_code == 404

    async def test_account_export_contains_only_own_data(self, client_factory, make_user):
        a = await make_user()
        b = await make_user()
        resp = await client_factory(a).get("/api/auth/account/export")
        assert resp.status_code == 200
        assert "attachment" in resp.headers["content-disposition"]
        payload = resp.text
        assert a.email in payload
        assert b.email not in payload
        assert "hashed_password" not in payload

    async def test_delete_account_requires_password_and_removes_user(
        self, client_factory, make_user, db_session
    ):
        user = await make_user()
        client = client_factory(user)
        bad = await client.request(
            "DELETE", "/api/auth/account", json={"password": "wrong-one-123"}
        )
        assert bad.status_code in (400, 401, 403)
        assert (await _fetch(db_session, user.id)) is not None

        ok = await client.request("DELETE", "/api/auth/account", json={"password": PASSWORD})
        assert ok.status_code == 200, ok.text
        gone = (
            await db_session.execute(select(User).where(User.id == user.id))
        ).scalar_one_or_none()
        assert gone is None

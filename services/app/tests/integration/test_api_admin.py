"""Integration tests for /api/admin: role gating, user lifecycle and invites.

Everything runs through the real `require_role("admin")` dependency with a
signed cookie, so a non-admin is rejected by the same code that rejects one in
production, and every state change is read back from Postgres.
"""

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select, text

from app.models.invite_code import InviteCode
from app.models.user import User
from app.services import email_service, user_service

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(loop_scope="session")
async def admin(make_user):
    return await make_user(role="admin", tier="pro")


@pytest_asyncio.fixture(loop_scope="session")
async def only_admin(admin, db_session):
    """Make `admin` the sole active admin (rolled back with the test)."""
    await db_session.execute(
        text("UPDATE users SET is_active = false WHERE role = 'admin' AND id != :id"),
        {"id": admin.id},
    )
    await db_session.flush()
    return admin


async def _row(db_session, user_id: str) -> User | None:
    result = await db_session.execute(
        select(User).where(User.id == user_id).execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


class TestRoleGate:
    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("GET", "/api/admin/users"),
            ("GET", "/api/admin/metrics"),
            ("GET", "/api/admin/funnel"),
            ("GET", "/api/admin/invites"),
            ("GET", "/api/admin/feedback"),
            ("POST", "/api/admin/invites"),
        ],
    )
    async def test_non_admin_forbidden_and_anonymous_unauthenticated(
        self, client_factory, make_user, method, path
    ):
        regular = await make_user(role="user")
        body = {} if method == "POST" else None
        denied = await client_factory(regular).request(method, path, json=body)
        assert denied.status_code == 403
        anon = await client_factory().request(method, path, json=body)
        assert anon.status_code == 401

    async def test_regular_user_cannot_modify_another_user(self, client_factory, make_user):
        regular = await make_user()
        victim = await make_user()
        resp = await client_factory(regular).patch(
            f"/api/admin/users/{victim.id}", json={"role": "admin"}
        )
        assert resp.status_code == 403
        resp = await client_factory(regular).delete(f"/api/admin/users/{victim.id}")
        assert resp.status_code == 403


class TestUsers:
    async def test_list_users_filters_and_paginates(self, client_factory, admin, make_user):
        pro = await make_user(tier="pro", username="pro_listed_user")
        free = await make_user(tier="free")
        client = client_factory(admin)

        resp = await client.get("/api/admin/users", params={"limit": 100})
        assert resp.status_code == 200
        ids = {u["id"] for u in resp.json()["users"]}
        assert {pro.id, free.id, admin.id} <= ids

        pros = (await client.get("/api/admin/users", params={"tier": "pro", "limit": 100})).json()
        assert pro.id in {u["id"] for u in pros["users"]}
        assert free.id not in {u["id"] for u in pros["users"]}

        page = (await client.get("/api/admin/users", params={"limit": 1, "offset": 0})).json()
        assert len(page["users"]) == 1 and page["total"] >= 3

        none = await client.get("/api/admin/users", params={"limit": 0})
        assert none.status_code == 422

    async def test_update_user_role_tier_and_session_revocation(
        self, client_factory, admin, make_user, db_session
    ):
        target = await make_user()
        client = client_factory(admin)
        resp = await client.patch(f"/api/admin/users/{target.id}", json={"tier": "pro"})
        assert resp.status_code == 200
        assert resp.json()["tier"] == "pro"
        assert resp.json()["sessions_revoked"] is False  # tier moves a quota, not a privilege

        resp = await client.patch(f"/api/admin/users/{target.id}", json={"role": "demo"})
        assert resp.json()["sessions_revoked"] is True
        fresh = await _row(db_session, target.id)
        assert fresh.role == "demo"
        assert fresh.tier == "pro"
        assert fresh.tokens_valid_from is not None

    async def test_update_user_echoing_current_values_revokes_nothing(
        self, client_factory, admin, make_user
    ):
        target = await make_user()
        resp = await client_factory(admin).patch(
            f"/api/admin/users/{target.id}", json={"role": "user", "is_active": True}
        )
        assert resp.status_code == 200
        assert resp.json()["sessions_revoked"] is False

    async def test_update_user_validation_and_not_found(self, client_factory, admin, make_user):
        target = await make_user()
        client = client_factory(admin)
        assert (await client.patch(f"/api/admin/users/{target.id}", json={})).status_code == 400
        bad = await client.patch(f"/api/admin/users/{target.id}", json={"role": "emperor"})
        assert bad.status_code == 422
        bad_tier = await client.patch(f"/api/admin/users/{target.id}", json={"tier": "platinum"})
        assert bad_tier.status_code == 422
        missing = await client.patch("/api/admin/users/does-not-exist", json={"tier": "pro"})
        assert missing.status_code == 404

    async def test_update_email_repoints_and_clears_verification(
        self, client_factory, admin, make_user, db_session
    ):
        target = await make_user(email_verified=True)
        resp = await client_factory(admin).patch(
            f"/api/admin/users/{target.id}", json={"email": "Corrected.Address@Example.com"}
        )
        assert resp.status_code == 200
        assert resp.json()["sessions_revoked"] is True
        fresh = await _row(db_session, target.id)
        assert fresh.email == "corrected.address@example.com"
        assert fresh.email_verified is False

    async def test_update_email_taken_by_other_account_conflicts(
        self, client_factory, admin, make_user
    ):
        a = await make_user()
        b = await make_user()
        resp = await client_factory(admin).patch(
            f"/api/admin/users/{a.id}", json={"email": b.email}
        )
        assert resp.status_code == 409

    async def test_last_admin_cannot_be_demoted_or_deactivated(
        self, client_factory, only_admin, db_session
    ):
        client = client_factory(only_admin)
        for body in ({"role": "user"}, {"is_active": False}):
            resp = await client.patch(f"/api/admin/users/{only_admin.id}", json=body)
            assert resp.status_code in (400, 409, 422)
        fresh = await _row(db_session, only_admin.id)
        assert fresh.role == "admin" and fresh.is_active is True

    async def test_create_user_returns_setup_link_and_no_password(
        self, client_factory, admin, db_session
    ):
        with patch.object(user_service, "deliver_password_reset", AsyncMock(return_value=True)):
            resp = await client_factory(admin).post(
                "/api/admin/users",
                json={"email": "Made.By.Admin@example.com", "username": "madebyadmin"},
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["email_sent"] is True
        assert "/reset-password?token=" in body["setup_url"]
        row = await _row(db_session, body["user"]["id"])
        assert row.hashed_password is None
        assert row.email == "made.by.admin@example.com"

    async def test_create_user_duplicate_and_bad_role(self, client_factory, admin, make_user):
        existing = await make_user()
        client = client_factory(admin)
        dup = await client.post(
            "/api/admin/users", json={"email": existing.email, "username": "freshname1"}
        )
        assert dup.status_code == 409
        bad = await client.post(
            "/api/admin/users",
            json={"email": "x1@example.com", "username": "xrole1", "role": "emperor"},
        )
        assert bad.status_code == 400

    async def test_delete_user_removes_row_but_not_self_or_unknown(
        self, client_factory, admin, make_user, db_session
    ):
        target = await make_user()
        client = client_factory(admin)
        ok = await client.delete(f"/api/admin/users/{target.id}")
        assert ok.status_code == 200
        assert await _row(db_session, target.id) is None

        assert (await client.delete(f"/api/admin/users/{admin.id}")).status_code == 400
        assert (await client.delete("/api/admin/users/nope")).status_code == 404
        assert await _row(db_session, admin.id) is not None

    async def test_password_reset_and_verification_links(self, client_factory, admin, make_user):
        target = await make_user(email_verified=False)
        client = client_factory(admin)
        with (
            patch.object(user_service, "deliver_password_reset", AsyncMock(return_value=True)),
            patch.object(user_service, "deliver_email_verification", AsyncMock(return_value=False)),
        ):
            reset = await client.post(f"/api/admin/users/{target.id}/password-reset")
            verify = await client.post(f"/api/admin/users/{target.id}/resend-verification")
        assert reset.status_code == 200 and reset.json()["email_sent"] is True
        assert "/reset-password?token=" in reset.json()["url"]
        assert verify.status_code == 200 and verify.json()["email_sent"] is False
        assert "/verify-email?token=" in verify.json()["url"]

        assert (await client.post("/api/admin/users/nope/password-reset")).status_code == 404
        assert (await client.post("/api/admin/users/nope/resend-verification")).status_code == 404

    async def test_resend_verification_for_verified_user_is_client_error(
        self, client_factory, admin, make_user
    ):
        target = await make_user(email_verified=True)
        resp = await client_factory(admin).post(f"/api/admin/users/{target.id}/resend-verification")
        assert resp.status_code == 400

    async def test_mfa_reset(self, client_factory, admin, make_user, db_session):
        target = await make_user()
        target.mfa_enabled = True
        target.mfa_secret = "JBSWY3DPEHPK3PXP"
        await db_session.flush()
        client = client_factory(admin)
        resp = await client.post(f"/api/admin/users/{target.id}/mfa-reset")
        assert resp.status_code == 200 and resp.json()["mfa_was_enabled"] is True
        fresh = await _row(db_session, target.id)
        assert fresh.mfa_enabled is False and fresh.mfa_secret is None
        assert fresh.tokens_valid_from is not None

        again = await client.post(f"/api/admin/users/{target.id}/mfa-reset")
        assert again.json()["mfa_was_enabled"] is False
        assert (await client.post("/api/admin/users/nope/mfa-reset")).status_code == 404

    async def test_user_details(self, client_factory, admin, make_user):
        target = await make_user()
        client = client_factory(admin)
        resp = await client.get(f"/api/admin/users/{target.id}/details")
        assert resp.status_code == 200
        body = resp.json()
        assert body["profile"]["id"] == target.id
        assert body["profile"]["email"] == target.email
        assert (await client.get("/api/admin/users/nope/details")).status_code == 404

    async def test_metrics_and_funnel_shapes(self, client_factory, admin, make_user):
        await make_user()
        client = client_factory(admin)
        metrics = (await client.get("/api/admin/metrics")).json()
        assert metrics["total_users"] >= 2
        assert metrics["total_storage_bytes"] >= 0
        funnel = await client.get("/api/admin/funnel", params={"include_admins": "true"})
        assert funnel.status_code == 200
        assert funnel.json()["include_admins"] is True
        assert funnel.json()["registered"] >= 2


class TestInvites:
    async def test_create_list_revoke_shared_invite(self, client_factory, admin, db_session):
        client = client_factory(admin)
        created = await client.post(
            "/api/admin/invites", json={"max_uses": 3, "note": "beta batch"}
        )
        assert created.status_code == 201
        invite = created.json()
        assert invite["max_uses"] == 3 and invite["is_redeemable"] is True
        assert invite["uses_remaining"] == 3

        listed = (await client.get("/api/admin/invites")).json()
        assert invite["id"] in {i["id"] for i in listed["invites"]}
        assert listed["total"] == len(listed["invites"])

        revoked = await client.delete(f"/api/admin/invites/{invite['id']}")
        assert revoked.status_code == 200
        assert revoked.json()["is_redeemable"] is False
        row = (
            await db_session.execute(
                select(InviteCode)
                .where(InviteCode.id == invite["id"])
                .execution_options(populate_existing=True)
            )
        ).scalar_one()
        assert row.revoked_at is not None  # revoked, not deleted

        assert (await client.delete("/api/admin/invites/nope")).status_code == 404

    async def test_invite_validation(self, client_factory, admin):
        resp = await client_factory(admin).post("/api/admin/invites", json={"max_uses": 0})
        assert resp.status_code == 422

    async def test_invite_is_redeemed_by_registration(self, client_factory, admin, db_session):
        code = (
            await client_factory(admin).post("/api/admin/invites", json={"max_uses": 1})
        ).json()["code"]
        with patch("app.config.settings.registration_mode", "invite"):
            anon = client_factory()
            ok = await anon.post(
                "/api/auth/register",
                json={
                    "email": "invited@example.com",
                    "username": "invitedperson",
                    "password": "correct-horse-battery",
                    "invite_code": code,
                },
            )
            assert ok.status_code == 201, ok.text
            # Used up: a second registration with the same code fails.
            second = await client_factory().post(
                "/api/auth/register",
                json={
                    "email": "invited2@example.com",
                    "username": "invitedperson2",
                    "password": "correct-horse-battery",
                    "invite_code": code,
                },
            )
        assert second.status_code >= 400
        user = (
            await db_session.execute(select(User).where(User.username == "invitedperson"))
        ).scalar_one()
        assert user.invite_code_id is not None
        absent = (
            await db_session.execute(select(User).where(User.username == "invitedperson2"))
        ).scalar_one_or_none()
        assert absent is None

    async def test_send_and_resend_email_invite(self, client_factory, admin):
        client = client_factory(admin)
        with patch.object(email_service, "send_invite", AsyncMock(return_value=True)) as send:
            sent = await client.post(
                "/api/admin/invites/send",
                json={"email": "friend@example.com", "note": "hi"},
            )
        assert sent.status_code == 201
        body = sent.json()
        assert body["email_sent"] is True
        assert "/register?invite=" in body["invite_url"]
        assert body["invite"]["email"] == "friend@example.com"
        assert body["invite"]["sent_at"] is not None
        send.assert_awaited_once()

        old_url = body["invite_url"]
        with patch.object(
            email_service, "send_invite", AsyncMock(side_effect=RuntimeError("smtp"))
        ):
            resent = await client.post(
                f"/api/admin/invites/{body['invite']['id']}/resend", json={"expires_in_days": 7}
            )
        assert resent.status_code == 200
        # SMTP failure never fails the request; the new link is in the response.
        assert resent.json()["email_sent"] is False
        assert resent.json()["invite_url"] != old_url

    async def test_send_invite_smtp_failure_still_returns_link(self, client_factory, admin):
        with patch.object(email_service, "send_invite", AsyncMock(side_effect=RuntimeError("x"))):
            resp = await client_factory(admin).post(
                "/api/admin/invites/send", json={"email": "nosmtp@example.com"}
            )
        assert resp.status_code == 201
        assert resp.json()["email_sent"] is False
        assert resp.json()["invite_url"]

    async def test_resend_rejects_shared_codes_and_unknown(self, client_factory, admin):
        client = client_factory(admin)
        shared = (await client.post("/api/admin/invites", json={})).json()
        resp = await client.post(f"/api/admin/invites/{shared['id']}/resend", json={})
        assert resp.status_code == 400
        assert (await client.post("/api/admin/invites/nope/resend", json={})).status_code == 404

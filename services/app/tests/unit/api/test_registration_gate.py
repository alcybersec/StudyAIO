"""Tests for the REGISTRATION_MODE gate on POST /api/auth/register.

The gate is enforced server-side. `/api/auth/config` only tells the frontend
what to render — a tester who posts straight to the API must hit the same wall.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import InviteError

REGISTER_BODY = {
    "email": "tester@example.com",
    "username": "tester",
    "password": "TestPass1!",
}


@pytest.fixture
def registered_user(make_user):
    """user_service.register_user returns a plain user."""
    return make_user(id="u-new", email="tester@example.com", username="tester")


class TestOpenMode:
    @pytest.mark.asyncio
    async def test_registration_succeeds_without_a_code(self, async_client, registered_user):
        with (
            patch("app.api.auth.settings") as cfg,
            patch(
                "app.api.auth.user_service.register_user", AsyncMock(return_value=registered_user)
            ),
            patch(
                "app.api.auth.user_service.create_email_verification_link",
                AsyncMock(return_value=MagicMock(raw_token="t")),
            ),
            patch(
                "app.api.auth.user_service.deliver_email_verification", AsyncMock(return_value=True)
            ),
        ):
            cfg.registration_mode = "open"
            cfg.cookie_secure = False
            cfg.cookie_samesite = "lax"
            cfg.jwt_access_token_expire_minutes = 15
            cfg.jwt_refresh_token_expire_days = 7
            resp = await async_client.post("/api/auth/register", json=REGISTER_BODY)

        assert resp.status_code == 201


class TestClosedMode:
    @pytest.mark.asyncio
    async def test_registration_is_rejected_with_403(self, async_client):
        with patch("app.api.auth.settings") as cfg:
            cfg.registration_mode = "closed"
            resp = await async_client.post("/api/auth/register", json=REGISTER_BODY)

        assert resp.status_code == 403
        assert "closed" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_a_valid_invite_code_does_not_bypass_closed(self, async_client):
        with patch("app.api.auth.settings") as cfg:
            cfg.registration_mode = "closed"
            resp = await async_client.post(
                "/api/auth/register", json={**REGISTER_BODY, "invite_code": "BETA-ABCD2345"}
            )

        assert resp.status_code == 403


class TestInviteMode:
    @pytest.mark.asyncio
    async def test_missing_code_is_rejected(self, async_client):
        with (
            patch("app.api.auth.settings") as cfg,
            patch(
                "app.api.auth.invite_service.redeem_invite",
                AsyncMock(side_effect=InviteError("An invite code is required to register")),
            ),
        ):
            cfg.registration_mode = "invite"
            resp = await async_client.post("/api/auth/register", json=REGISTER_BODY)

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_invalid_code_is_rejected(self, async_client):
        with (
            patch("app.api.auth.settings") as cfg,
            patch(
                "app.api.auth.invite_service.redeem_invite",
                AsyncMock(side_effect=InviteError("That invite code is not valid")),
            ),
        ):
            cfg.registration_mode = "invite"
            resp = await async_client.post(
                "/api/auth/register", json={**REGISTER_BODY, "invite_code": "BETA-WRONG123"}
            )

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_no_user_is_created_when_the_code_is_bad(self, async_client):
        """The code is redeemed first, so a bad code must not cost a username."""
        register = AsyncMock()
        with (
            patch("app.api.auth.settings") as cfg,
            patch(
                "app.api.auth.invite_service.redeem_invite",
                AsyncMock(side_effect=InviteError("That invite code is not valid")),
            ),
            patch("app.api.auth.user_service.register_user", register),
        ):
            cfg.registration_mode = "invite"
            await async_client.post(
                "/api/auth/register", json={**REGISTER_BODY, "invite_code": "BETA-WRONG123"}
            )

        register.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_valid_code_registers_and_is_recorded(self, async_client, registered_user):
        invite = MagicMock(id="inv-1")
        with (
            patch("app.api.auth.settings") as cfg,
            patch("app.api.auth.invite_service.redeem_invite", AsyncMock(return_value=invite)),
            patch(
                "app.api.auth.user_service.register_user", AsyncMock(return_value=registered_user)
            ),
            patch(
                "app.api.auth.user_service.create_email_verification_link",
                AsyncMock(return_value=MagicMock(raw_token="t")),
            ),
            patch(
                "app.api.auth.user_service.deliver_email_verification", AsyncMock(return_value=True)
            ),
        ):
            cfg.registration_mode = "invite"
            cfg.cookie_secure = False
            cfg.cookie_samesite = "lax"
            cfg.jwt_access_token_expire_minutes = 15
            cfg.jwt_refresh_token_expire_days = 7
            resp = await async_client.post(
                "/api/auth/register", json={**REGISTER_BODY, "invite_code": "BETA-ABCD2345"}
            )

        assert resp.status_code == 201
        # The account records which invite it used, so a leaked code is traceable.
        assert registered_user.invite_code_id == "inv-1"


class TestAuthConfigAdvertisesTheMode:
    @pytest.mark.asyncio
    async def test_invite_mode_sets_invite_required(self, async_client):
        with patch("app.api.auth.settings") as cfg:
            cfg.registration_mode = "invite"
            cfg.self_hosted = False
            cfg.google_client_id = ""
            cfg.github_client_id = ""
            cfg.demo_enabled = False
            resp = await async_client.get("/api/auth/config")

        data = resp.json()
        assert data["registration_mode"] == "invite"
        assert data["invite_required"] is True
        assert data["registration_enabled"] is True

    @pytest.mark.asyncio
    async def test_closed_mode_disables_registration(self, async_client):
        with patch("app.api.auth.settings") as cfg:
            cfg.registration_mode = "closed"
            cfg.self_hosted = False
            cfg.google_client_id = ""
            cfg.github_client_id = ""
            cfg.demo_enabled = False
            resp = await async_client.get("/api/auth/config")

        data = resp.json()
        assert data["registration_enabled"] is False
        assert data["invite_required"] is False

    @pytest.mark.asyncio
    async def test_open_mode_needs_no_code(self, async_client):
        with patch("app.api.auth.settings") as cfg:
            cfg.registration_mode = "open"
            cfg.self_hosted = False
            cfg.google_client_id = ""
            cfg.github_client_id = ""
            cfg.demo_enabled = False
            resp = await async_client.get("/api/auth/config")

        data = resp.json()
        assert data["invite_required"] is False
        assert data["registration_enabled"] is True

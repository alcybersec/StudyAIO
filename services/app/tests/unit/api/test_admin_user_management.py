"""Tests for the admin user provisioning and lifecycle endpoints.

The fixtures mirror `test_admin_api.py` so both files authenticate the same way.
"""

import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.models.user import User


def _make_user(**overrides) -> MagicMock:
    user = MagicMock(spec=User)
    user.id = overrides.get("id", "u-1")
    user.email = overrides.get("email", "tester@example.com")
    user.username = overrides.get("username", "tester")
    user.role = overrides.get("role", "user")
    user.tier = overrides.get("tier", "free")
    user.is_active = overrides.get("is_active", True)
    user.email_verified = overrides.get("email_verified", False)
    user.created_at = overrides.get("created_at")
    user.last_login_at = None
    return user


@pytest.fixture
async def admin_client(mock_session):
    """Client authenticated as an admin."""
    from app.api.deps import get_current_user
    from app.core.database import get_session
    from app.core.rate_limit import limiter
    from app.main import app

    admin = _make_user(id="admin-001", email="admin@example.com", username="admin", role="admin")

    async def override_session():
        yield mock_session

    async def override_user():
        return admin

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = override_user
    limiter.reset()

    with tempfile.TemporaryDirectory() as tmpdir, patch("app.config.settings.data_dir", tmpdir):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client
    app.dependency_overrides.clear()


@pytest.fixture
async def nonadmin_client(mock_session):
    """Client authenticated as a regular user."""
    from app.api.deps import get_current_user
    from app.core.database import get_session
    from app.core.rate_limit import limiter
    from app.main import app

    async def override_session():
        yield mock_session

    async def override_user():
        return _make_user(id="user-001", role="user")

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = override_user
    limiter.reset()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    app.dependency_overrides.clear()


NEW_USER = {"email": "newbie@example.com", "username": "newbie"}


class TestCreateUserEndpoint:
    @pytest.mark.asyncio
    async def test_returns_the_setup_link(self, admin_client):
        created = _make_user(id="u-new", email="newbie@example.com", username="newbie")
        with (
            patch(
                "app.api.admin.admin_service.create_user",
                AsyncMock(return_value=(created, "raw-token-abc")),
            ),
            patch(
                "app.api.admin.user_service.deliver_password_reset",
                AsyncMock(return_value=True),
            ),
        ):
            resp = await admin_client.post("/api/admin/users", json=NEW_USER)

        assert resp.status_code == 201
        body = resp.json()
        assert "raw-token-abc" in body["setup_url"]
        assert body["setup_url"].startswith("http")
        assert "/reset-password?token=" in body["setup_url"]
        assert body["email_sent"] is True
        assert body["user"]["email"] == "newbie@example.com"

    @pytest.mark.asyncio
    async def test_link_is_returned_even_when_email_fails(self, admin_client):
        """A beta instance often has no SMTP; the admin still needs the link."""
        created = _make_user(id="u-new")
        with (
            patch(
                "app.api.admin.admin_service.create_user",
                AsyncMock(return_value=(created, "raw-token-abc")),
            ),
            patch(
                "app.api.admin.user_service.deliver_password_reset",
                AsyncMock(side_effect=RuntimeError("no smtp")),
            ),
        ):
            resp = await admin_client.post("/api/admin/users", json=NEW_USER)

        assert resp.status_code == 201
        assert resp.json()["email_sent"] is False
        assert "raw-token-abc" in resp.json()["setup_url"]

    @pytest.mark.asyncio
    async def test_duplicate_email_returns_409(self, admin_client):
        from app.core.exceptions import UserExistsError

        with patch(
            "app.api.admin.admin_service.create_user",
            AsyncMock(side_effect=UserExistsError("email")),
        ):
            resp = await admin_client.post("/api/admin/users", json=NEW_USER)

        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_bad_role_returns_400(self, admin_client):
        with patch(
            "app.api.admin.admin_service.create_user",
            AsyncMock(side_effect=ValueError("role must be one of ['admin', 'user']")),
        ):
            resp = await admin_client.post(
                "/api/admin/users", json={**NEW_USER, "role": "superuser"}
            )

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_invalid_email_returns_422(self, admin_client):
        resp = await admin_client.post(
            "/api/admin/users", json={"email": "not-an-email", "username": "x"}
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_non_admin_is_forbidden(self, nonadmin_client):
        resp = await nonadmin_client.post("/api/admin/users", json=NEW_USER)
        assert resp.status_code == 403


class TestDeleteUserEndpoint:
    @pytest.mark.asyncio
    async def test_deletes_and_reports_row_count(self, admin_client):
        with patch(
            "app.api.admin.admin_service.delete_user",
            AsyncMock(return_value={"users": 1, "courses": 3}),
        ):
            resp = await admin_client.delete("/api/admin/users/u-1")

        assert resp.status_code == 200
        assert resp.json()["rows_deleted"] == 4

    @pytest.mark.asyncio
    async def test_unknown_user_returns_404(self, admin_client):
        with patch(
            "app.api.admin.admin_service.delete_user",
            AsyncMock(side_effect=ValueError("User not found")),
        ):
            resp = await admin_client.delete("/api/admin/users/nope")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_self_deletion_returns_400(self, admin_client):
        with patch(
            "app.api.admin.admin_service.delete_user",
            AsyncMock(
                side_effect=ValueError("You cannot delete your own account from the admin panel")
            ),
        ):
            resp = await admin_client.delete("/api/admin/users/admin-001")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_last_admin_returns_400(self, admin_client):
        with patch(
            "app.api.admin.admin_service.delete_user",
            AsyncMock(side_effect=ValueError("Cannot delete the last active admin")),
        ):
            resp = await admin_client.delete("/api/admin/users/admin-002")
        assert resp.status_code == 400
        assert "last active admin" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_non_admin_is_forbidden(self, nonadmin_client):
        resp = await nonadmin_client.delete("/api/admin/users/u-1")
        assert resp.status_code == 403


class TestPasswordResetEndpoint:
    @pytest.mark.asyncio
    async def test_returns_a_reset_link(self, admin_client):
        with (
            patch(
                "app.api.admin.admin_service.issue_password_reset",
                AsyncMock(return_value=(_make_user(), "tok-reset")),
            ),
            patch(
                "app.api.admin.user_service.deliver_password_reset",
                AsyncMock(return_value=True),
            ),
        ):
            resp = await admin_client.post("/api/admin/users/u-1/password-reset")

        assert resp.status_code == 200
        assert "tok-reset" in resp.json()["url"]
        assert resp.json()["email_sent"] is True

    @pytest.mark.asyncio
    async def test_unknown_user_returns_404(self, admin_client):
        with patch(
            "app.api.admin.admin_service.issue_password_reset",
            AsyncMock(side_effect=ValueError("User not found")),
        ):
            resp = await admin_client.post("/api/admin/users/nope/password-reset")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_non_admin_is_forbidden(self, nonadmin_client):
        resp = await nonadmin_client.post("/api/admin/users/u-1/password-reset")
        assert resp.status_code == 403


class TestResendVerificationEndpoint:
    @pytest.mark.asyncio
    async def test_returns_a_verification_link(self, admin_client):
        with (
            patch(
                "app.api.admin.admin_service.issue_email_verification",
                AsyncMock(return_value=(_make_user(), "tok-verify")),
            ),
            patch(
                "app.api.admin.user_service.deliver_email_verification",
                AsyncMock(return_value=True),
            ),
        ):
            resp = await admin_client.post("/api/admin/users/u-1/resend-verification")

        assert resp.status_code == 200
        assert "tok-verify" in resp.json()["url"]
        assert "/verify-email?token=" in resp.json()["url"]

    @pytest.mark.asyncio
    async def test_already_verified_returns_400(self, admin_client):
        with patch(
            "app.api.admin.admin_service.issue_email_verification",
            AsyncMock(side_effect=ValueError("This email is already verified")),
        ):
            resp = await admin_client.post("/api/admin/users/u-1/resend-verification")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_non_admin_is_forbidden(self, nonadmin_client):
        resp = await nonadmin_client.post("/api/admin/users/u-1/resend-verification")
        assert resp.status_code == 403


class TestTierChangeStillWorks:
    """Tier is changed through the existing PATCH endpoint."""

    @pytest.mark.asyncio
    async def test_patch_updates_tier(self, admin_client):
        # admin_service.update_user returns a dict, not an ORM object.
        updated = {
            "id": "u-1",
            "email": "tester@example.com",
            "username": "tester",
            "role": "user",
            "tier": "pro",
            "is_active": True,
            "created_at": None,
            "last_login_at": None,
        }
        with patch("app.api.admin.admin_service.update_user", AsyncMock(return_value=updated)):
            resp = await admin_client.patch("/api/admin/users/u-1", json={"tier": "pro"})

        assert resp.status_code == 200
        assert resp.json()["tier"] == "pro"

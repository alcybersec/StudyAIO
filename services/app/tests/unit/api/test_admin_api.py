"""Tests for admin API endpoints."""

import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.models.user import User


def _make_admin_user():
    """Create a mock admin User."""
    user = MagicMock(spec=User)
    user.id = "admin-001"
    user.email = "admin@test.com"
    user.username = "admin"
    user.role = "admin"
    user.tier = "pro"
    user.is_active = True
    user.email_verified = True
    return user


def _make_regular_user():
    """Create a mock non-admin User."""
    user = MagicMock(spec=User)
    user.id = "user-001"
    user.email = "user@test.com"
    user.username = "testuser"
    user.role = "user"
    user.tier = "free"
    user.is_active = True
    user.email_verified = True
    return user


@pytest.fixture
async def admin_client(mock_session):
    """Async client authenticated as admin via get_current_user."""
    from app.api.deps import get_current_user
    from app.core.database import get_session
    from app.main import app

    admin_user = _make_admin_user()

    async def override_session():
        yield mock_session

    async def override_user():
        return admin_user

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = override_user

    from app.core.rate_limit import limiter

    limiter.reset()

    with tempfile.TemporaryDirectory() as tmpdir, patch("app.config.settings.data_dir", tmpdir):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client
    app.dependency_overrides.clear()


@pytest.fixture
async def nonadmin_client(mock_session):
    """Async client authenticated as regular user via get_current_user."""
    from app.api.deps import get_current_user
    from app.core.database import get_session
    from app.main import app

    regular_user = _make_regular_user()

    async def override_session():
        yield mock_session

    async def override_user():
        return regular_user

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = override_user

    from app.core.rate_limit import limiter

    limiter.reset()

    with tempfile.TemporaryDirectory() as tmpdir, patch("app.config.settings.data_dir", tmpdir):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
class TestAdminListUsers:
    """Tests for GET /api/admin/users."""

    async def test_list_users_as_admin(self, admin_client):
        """Admin can list users."""
        mock_users = [
            {
                "id": "u-1",
                "email": "a@test.com",
                "username": "alice",
                "role": "user",
                "tier": "free",
                "is_active": True,
                "created_at": "2025-01-01T00:00:00",
                "last_login_at": None,
            }
        ]
        with patch(
            "app.api.admin.admin_service.list_users",
            new_callable=AsyncMock,
            return_value=(mock_users, 1),
        ):
            response = await admin_client.get("/api/admin/users")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["users"]) == 1
        assert data["users"][0]["email"] == "a@test.com"

    async def test_list_users_forbidden_for_non_admin(self, nonadmin_client):
        """Non-admin gets 403."""
        response = await nonadmin_client.get("/api/admin/users")
        assert response.status_code == 403


@pytest.mark.asyncio
class TestAdminUpdateUser:
    """Tests for PATCH /api/admin/users/{user_id}."""

    async def test_update_user_as_admin(self, admin_client):
        """Admin can update user role."""
        mock_result = {
            "id": "u-1",
            "email": "a@test.com",
            "username": "alice",
            "role": "admin",
            "tier": "free",
            "is_active": True,
            "created_at": "2025-01-01T00:00:00",
            "last_login_at": None,
        }
        with patch(
            "app.api.admin.admin_service.update_user",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            response = await admin_client.patch(
                "/api/admin/users/u-1",
                json={"role": "admin"},
            )

        assert response.status_code == 200
        assert response.json()["role"] == "admin"

    async def test_update_user_not_found(self, admin_client):
        """Admin gets 404 for nonexistent user."""
        with patch(
            "app.api.admin.admin_service.update_user",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = await admin_client.patch(
                "/api/admin/users/nonexistent",
                json={"role": "admin"},
            )

        assert response.status_code == 404

    async def test_update_user_forbidden_for_non_admin(self, nonadmin_client):
        """Non-admin gets 403."""
        response = await nonadmin_client.patch(
            "/api/admin/users/u-1",
            json={"role": "admin"},
        )
        assert response.status_code == 403

    async def test_update_user_empty_body_returns_400(self, admin_client):
        """Empty update body returns 400."""
        response = await admin_client.patch(
            "/api/admin/users/u-1",
            json={},
        )
        assert response.status_code == 400


@pytest.mark.asyncio
class TestAdminMetrics:
    """Tests for GET /api/admin/metrics."""

    async def test_get_metrics_as_admin(self, admin_client):
        """Admin can view system metrics."""
        mock_metrics = {
            "total_users": 10,
            "total_artifacts": 50,
            "total_courses": 3,
            "pipeline_runs_24h": 7,
            "total_storage_bytes": 104857600,
            "total_storage_mb": 100.0,
        }
        with patch(
            "app.api.admin.admin_service.get_system_metrics",
            new_callable=AsyncMock,
            return_value=mock_metrics,
        ):
            response = await admin_client.get("/api/admin/metrics")

        assert response.status_code == 200
        data = response.json()
        assert data["total_users"] == 10
        assert data["total_storage_mb"] == 100.0

    async def test_get_metrics_forbidden_for_non_admin(self, nonadmin_client):
        """Non-admin gets 403."""
        response = await nonadmin_client.get("/api/admin/metrics")
        assert response.status_code == 403

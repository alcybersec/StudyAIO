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

    async def test_update_user_email_only(self, admin_client):
        """Admin can correct a user's address with no other field set."""
        mock_result = {
            "id": "u-1",
            "email": "real@example.com",
            "username": "alice",
            "role": "user",
            "tier": "free",
            "is_active": True,
            "created_at": "2025-01-01T00:00:00",
            "last_login_at": None,
        }
        with patch(
            "app.api.admin.admin_service.update_user",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_update:
            response = await admin_client.patch(
                "/api/admin/users/u-1",
                json={"email": "real@example.com"},
            )

        assert response.status_code == 200
        assert response.json()["email"] == "real@example.com"
        assert mock_update.call_args.kwargs["email"] == "real@example.com"

    async def test_update_user_invalid_email_returns_422(self, admin_client):
        """A malformed address is rejected before it ever reaches the service."""
        with patch(
            "app.api.admin.admin_service.update_user",
            new_callable=AsyncMock,
        ) as mock_update:
            response = await admin_client.patch(
                "/api/admin/users/u-1",
                json={"email": "not-an-email"},
            )

        assert response.status_code == 422
        mock_update.assert_not_called()


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


def _sample_user_detail():
    """Create a full user detail response dict."""
    return {
        "profile": {
            "id": "u-1",
            "email": "alice@test.com",
            "username": "alice",
            "role": "user",
            "tier": "free",
            "is_active": True,
            "email_verified": True,
            "mfa_enabled": False,
            "avatar_url": None,
            "last_login_at": "2026-03-01T08:00:00",
            "created_at": "2026-01-01T00:00:00",
        },
        "subscription": {
            "plan": "free",
            "status": "active",
            "current_period_start": "2026-01-01T00:00:00",
            "current_period_end": "2026-02-01T00:00:00",
            "cancel_at_period_end": False,
        },
        "storage": {
            "total_bytes": 1048576,
            "total_mb": 1.0,
            "total_files": 5,
            "status_breakdown": {"processed": 4, "ingested": 1},
        },
        "usage": {
            "today": {"ai_calls": 3, "tokens_input": 1500, "tokens_output": 800, "uploads": 1},
            "last_30_days": {
                "ai_calls": 50,
                "tokens_input": 30000,
                "tokens_output": 15000,
                "uploads": 10,
            },
        },
        "pipeline": {
            "total_runs": 20,
            "success_count": 18,
            "failed_count": 2,
            "avg_duration_ms": 5000,
            "stages": [
                {"stage": "ingest", "total": 5, "success": 5, "failed": 0},
                {"stage": "classify", "total": 5, "success": 4, "failed": 1},
            ],
            "recent_failures": [
                {
                    "stage": "classify",
                    "error_message": "Timeout",
                    "started_at": "2026-03-10T10:00:00",
                },
            ],
        },
        "study": {
            "total_sessions": 15,
            "cards_reviewed": 200,
            "quiz_questions_answered": 80,
            "quiz_correct": 65,
            "quiz_accuracy_pct": 81.3,
            "total_study_hours": 12.5,
        },
        "content": {
            "courses_count": 2,
            "artifacts_count": 10,
            "exams_count": 3,
            "per_course": [
                {"code": "CSIT302", "name": "Cybersecurity", "artifact_count": 6},
                {"code": "CSIT314", "name": "Software Dev", "artifact_count": 4},
            ],
        },
        "gamification": {"total_xp": 1500, "level": 5, "achievements_count": 8},
        "chat": {"total_sessions": 10, "total_messages": 50, "total_tokens": 25000},
    }


@pytest.mark.asyncio
class TestAdminUserDetails:
    """Tests for GET /api/admin/users/{user_id}/details."""

    async def test_get_user_details_success(self, admin_client):
        """Admin can get user details."""
        with (
            patch(
                "app.api.admin.cache_get",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.api.admin.cache_set",
                new_callable=AsyncMock,
            ),
            patch(
                "app.api.admin.admin_service.get_user_details",
                new_callable=AsyncMock,
                return_value=_sample_user_detail(),
            ),
        ):
            response = await admin_client.get("/api/admin/users/u-1/details")

        assert response.status_code == 200
        data = response.json()
        assert data["profile"]["id"] == "u-1"
        assert data["profile"]["email"] == "alice@test.com"
        assert data["subscription"]["plan"] == "free"
        assert data["storage"]["total_files"] == 5
        assert data["pipeline"]["total_runs"] == 20
        assert data["study"]["total_sessions"] == 15
        assert data["content"]["courses_count"] == 2
        assert data["gamification"]["total_xp"] == 1500
        assert data["chat"]["total_sessions"] == 10

    async def test_get_user_details_not_found(self, admin_client):
        """Admin gets 404 for nonexistent user."""
        with (
            patch(
                "app.api.admin.cache_get",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.api.admin.admin_service.get_user_details",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            response = await admin_client.get("/api/admin/users/nonexistent/details")

        assert response.status_code == 404

    async def test_get_user_details_forbidden_for_non_admin(self, nonadmin_client):
        """Non-admin gets 403."""
        response = await nonadmin_client.get("/api/admin/users/u-1/details")
        assert response.status_code == 403

    async def test_get_user_details_cache_hit(self, admin_client):
        """Cached response is returned without calling the service."""
        cached_data = _sample_user_detail()
        with (
            patch(
                "app.api.admin.cache_get",
                new_callable=AsyncMock,
                return_value=cached_data,
            ) as mock_cache,
            patch(
                "app.api.admin.admin_service.get_user_details",
                new_callable=AsyncMock,
            ) as mock_service,
        ):
            response = await admin_client.get("/api/admin/users/u-1/details")

        assert response.status_code == 200
        mock_cache.assert_called_once()
        mock_service.assert_not_called()

    async def test_get_user_details_with_null_sections(self, admin_client):
        """Response with null optional sections validates correctly."""
        minimal = {
            "profile": _sample_user_detail()["profile"],
            "subscription": None,
            "storage": None,
            "usage": None,
            "pipeline": None,
            "study": None,
            "content": None,
            "gamification": None,
            "chat": None,
        }
        with (
            patch(
                "app.api.admin.cache_get",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.api.admin.cache_set",
                new_callable=AsyncMock,
            ),
            patch(
                "app.api.admin.admin_service.get_user_details",
                new_callable=AsyncMock,
                return_value=minimal,
            ),
        ):
            response = await admin_client.get("/api/admin/users/u-1/details")

        assert response.status_code == 200
        data = response.json()
        assert data["profile"]["id"] == "u-1"
        assert data["subscription"] is None
        assert data["storage"] is None
        assert data["pipeline"] is None

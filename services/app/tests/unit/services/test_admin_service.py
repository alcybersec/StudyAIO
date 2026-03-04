"""Tests for admin service — user management and system metrics."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import admin_service


@pytest.fixture
def mock_session():
    """AsyncMock of AsyncSession."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


def _make_user_model(
    id="user-001",
    email="test@example.com",
    username="testuser",
    role="user",
    tier="free",
    is_active=True,
):
    """Create a mock User model object."""
    user = MagicMock()
    user.id = id
    user.email = email
    user.username = username
    user.role = role
    user.tier = tier
    user.is_active = is_active
    user.created_at = datetime(2025, 1, 15, 10, 0, 0)
    user.last_login_at = datetime(2025, 6, 1, 12, 0, 0)
    user.updated_at = datetime(2025, 6, 1, 12, 0, 0)
    return user


@pytest.mark.asyncio
class TestListUsers:
    """Tests for list_users()."""

    async def test_returns_users_and_count(self, mock_session):
        """list_users returns list of user dicts and total count."""
        user1 = _make_user_model(id="u-1", email="a@test.com")
        user2 = _make_user_model(id="u-2", email="b@test.com")

        # Mock count query
        count_result = MagicMock()
        count_result.scalar_one.return_value = 2

        # Mock user query
        user_result = MagicMock()
        user_scalars = MagicMock()
        user_scalars.all.return_value = [user1, user2]
        user_result.scalars.return_value = user_scalars

        mock_session.execute = AsyncMock(side_effect=[count_result, user_result])

        users, total = await admin_service.list_users(mock_session)
        assert total == 2
        assert len(users) == 2
        assert users[0]["id"] == "u-1"
        assert users[1]["id"] == "u-2"

    async def test_returns_empty_list(self, mock_session):
        """list_users returns empty when no users match."""
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0

        user_result = MagicMock()
        user_scalars = MagicMock()
        user_scalars.all.return_value = []
        user_result.scalars.return_value = user_scalars

        mock_session.execute = AsyncMock(side_effect=[count_result, user_result])

        users, total = await admin_service.list_users(mock_session, role="demo")
        assert total == 0
        assert users == []


@pytest.mark.asyncio
class TestUpdateUser:
    """Tests for update_user()."""

    async def test_update_role(self, mock_session):
        """update_user changes role and returns updated dict."""
        user = _make_user_model()
        mock_session.get = AsyncMock(return_value=user)

        result = await admin_service.update_user(mock_session, "user-001", role="admin")
        assert result is not None
        assert user.role == "admin"
        mock_session.commit.assert_called_once()

    async def test_update_not_found(self, mock_session):
        """update_user returns None when user doesn't exist."""
        mock_session.get = AsyncMock(return_value=None)

        result = await admin_service.update_user(mock_session, "nonexistent", role="admin")
        assert result is None
        mock_session.commit.assert_not_called()

    async def test_update_invalid_role_raises(self, mock_session):
        """update_user raises ValueError for invalid role."""
        user = _make_user_model()
        mock_session.get = AsyncMock(return_value=user)

        with pytest.raises(ValueError, match="Invalid role"):
            await admin_service.update_user(mock_session, "user-001", role="superadmin")

    async def test_update_tier(self, mock_session):
        """update_user changes tier."""
        user = _make_user_model()
        mock_session.get = AsyncMock(return_value=user)

        result = await admin_service.update_user(mock_session, "user-001", tier="pro")
        assert result is not None
        assert user.tier == "pro"

    async def test_update_deactivate(self, mock_session):
        """update_user can deactivate a user."""
        user = _make_user_model()
        mock_session.get = AsyncMock(return_value=user)

        result = await admin_service.update_user(mock_session, "user-001", is_active=False)
        assert result is not None
        assert user.is_active is False


@pytest.mark.asyncio
class TestGetSystemMetrics:
    """Tests for get_system_metrics()."""

    async def test_returns_all_metrics(self, mock_session):
        """get_system_metrics returns all expected metric keys."""
        # Mock 5 sequential queries: users, artifacts, courses, pipeline_runs, storage
        results = []
        for val in [10, 50, 3, 7, 1024 * 1024 * 100]:  # 100 MB
            r = MagicMock()
            r.scalar_one.return_value = val
            results.append(r)

        mock_session.execute = AsyncMock(side_effect=results)

        metrics = await admin_service.get_system_metrics(mock_session)
        assert metrics["total_users"] == 10
        assert metrics["total_artifacts"] == 50
        assert metrics["total_courses"] == 3
        assert metrics["pipeline_runs_24h"] == 7
        assert metrics["total_storage_bytes"] == 1024 * 1024 * 100
        assert metrics["total_storage_mb"] == 100.0

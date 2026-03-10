"""Golden tests for admin response structures.

Validates that admin-related data conforms to expected schemas:
- UserResponse: admin view of a user (id, email, role, tier, active, timestamps)
- SystemMetricsResponse: aggregate system metrics (users, artifacts, courses, pipeline, storage)
- UserListResponse: paginated user list envelope
- UserUpdateRequest: allowed update fields
"""

import pytest

from app.api.admin import (
    SystemMetricsResponse,
    UserListResponse,
    UserResponse,
    UserUpdateRequest,
)

# -- Sample data fixtures ---------------------------------------------------


@pytest.fixture
def sample_user_response():
    """A realistic admin UserResponse dict."""
    return {
        "id": "user-001",
        "email": "alice@example.com",
        "username": "alice",
        "role": "user",
        "tier": "free",
        "is_active": True,
        "created_at": "2026-01-15T10:00:00",
        "last_login_at": "2026-03-01T08:30:00",
    }


@pytest.fixture
def sample_admin_user_response():
    """An admin user response."""
    return {
        "id": "admin-001",
        "email": "admin@studyaio.local",
        "username": "admin",
        "role": "admin",
        "tier": "pro",
        "is_active": True,
        "created_at": "2025-06-01T00:00:00",
        "last_login_at": None,
    }


@pytest.fixture
def sample_system_metrics():
    """A realistic system metrics response."""
    return {
        "total_users": 42,
        "total_artifacts": 256,
        "total_courses": 8,
        "pipeline_runs_24h": 15,
        "total_storage_bytes": 536870912,
        "total_storage_mb": 512.0,
    }


@pytest.fixture
def sample_user_list_response(sample_user_response, sample_admin_user_response):
    """A paginated user list response."""
    return {
        "users": [sample_admin_user_response, sample_user_response],
        "total": 2,
        "offset": 0,
        "limit": 50,
    }


# -- UserResponse structure --------------------------------------------------


class TestUserResponseStructure:
    """Validate admin UserResponse schema structure."""

    def test_has_required_fields(self, sample_user_response) -> None:
        """UserResponse has all required fields."""
        required = {
            "id",
            "email",
            "username",
            "role",
            "tier",
            "is_active",
            "created_at",
            "last_login_at",
        }
        missing = required - sample_user_response.keys()
        assert not missing, f"Missing fields: {missing}"

    def test_pydantic_model_accepts_valid_data(self, sample_user_response) -> None:
        """UserResponse Pydantic model accepts valid data."""
        model = UserResponse(**sample_user_response)
        assert model.id == "user-001"
        assert model.email == "alice@example.com"
        assert model.role == "user"
        assert model.tier == "free"
        assert model.is_active is True

    def test_pydantic_model_accepts_none_timestamps(self, sample_admin_user_response) -> None:
        """UserResponse allows None for last_login_at."""
        model = UserResponse(**sample_admin_user_response)
        assert model.last_login_at is None

    def test_id_is_string(self, sample_user_response) -> None:
        """User ID is a string."""
        assert isinstance(sample_user_response["id"], str)
        assert len(sample_user_response["id"]) > 0

    def test_role_is_valid(self, sample_user_response) -> None:
        """Role is one of the allowed values."""
        valid_roles = {"admin", "user", "demo"}
        assert sample_user_response["role"] in valid_roles

    def test_tier_is_valid(self, sample_user_response) -> None:
        """Tier is one of the allowed values."""
        valid_tiers = {"free", "pro"}
        assert sample_user_response["tier"] in valid_tiers

    def test_is_active_is_bool(self, sample_user_response) -> None:
        """is_active is a boolean."""
        assert isinstance(sample_user_response["is_active"], bool)


# -- SystemMetricsResponse structure -----------------------------------------


class TestSystemMetricsResponseStructure:
    """Validate SystemMetricsResponse schema structure."""

    def test_has_required_fields(self, sample_system_metrics) -> None:
        """SystemMetrics has all required fields."""
        required = {
            "total_users",
            "total_artifacts",
            "total_courses",
            "pipeline_runs_24h",
            "total_storage_bytes",
            "total_storage_mb",
        }
        missing = required - sample_system_metrics.keys()
        assert not missing, f"Missing fields: {missing}"

    def test_pydantic_model_accepts_valid_data(self, sample_system_metrics) -> None:
        """SystemMetricsResponse Pydantic model accepts valid data."""
        model = SystemMetricsResponse(**sample_system_metrics)
        assert model.total_users == 42
        assert model.total_artifacts == 256
        assert model.total_courses == 8
        assert model.pipeline_runs_24h == 15
        assert model.total_storage_bytes == 536870912
        assert model.total_storage_mb == 512.0

    def test_counts_are_non_negative_integers(self, sample_system_metrics) -> None:
        """All count fields are non-negative integers."""
        int_fields = [
            "total_users",
            "total_artifacts",
            "total_courses",
            "pipeline_runs_24h",
            "total_storage_bytes",
        ]
        for field in int_fields:
            value = sample_system_metrics[field]
            assert isinstance(value, int), f"{field} should be int, got {type(value)}"
            assert value >= 0, f"{field} should be non-negative"

    def test_storage_mb_is_float(self, sample_system_metrics) -> None:
        """total_storage_mb is a float."""
        assert isinstance(sample_system_metrics["total_storage_mb"], (int, float))
        assert sample_system_metrics["total_storage_mb"] >= 0

    def test_storage_mb_matches_bytes(self, sample_system_metrics) -> None:
        """Storage MB is consistent with bytes."""
        expected_mb = round(sample_system_metrics["total_storage_bytes"] / (1024 * 1024), 2)
        assert sample_system_metrics["total_storage_mb"] == expected_mb


# -- UserListResponse structure -----------------------------------------------


class TestUserListResponseStructure:
    """Validate UserListResponse schema structure."""

    def test_has_required_fields(self, sample_user_list_response) -> None:
        """UserListResponse has users, total, offset, limit."""
        required = {"users", "total", "offset", "limit"}
        missing = required - sample_user_list_response.keys()
        assert not missing, f"Missing fields: {missing}"

    def test_pydantic_model_accepts_valid_data(self, sample_user_list_response) -> None:
        """UserListResponse Pydantic model accepts valid data."""
        model = UserListResponse(**sample_user_list_response)
        assert model.total == 2
        assert model.offset == 0
        assert model.limit == 50
        assert len(model.users) == 2

    def test_users_is_list(self, sample_user_list_response) -> None:
        """users field is a list."""
        assert isinstance(sample_user_list_response["users"], list)

    def test_total_matches_or_exceeds_users_length(self, sample_user_list_response) -> None:
        """total >= len(users) (total is the unpaginated count)."""
        assert sample_user_list_response["total"] >= len(sample_user_list_response["users"])

    def test_offset_is_non_negative(self, sample_user_list_response) -> None:
        """offset is non-negative."""
        assert sample_user_list_response["offset"] >= 0

    def test_limit_is_positive(self, sample_user_list_response) -> None:
        """limit is a positive integer."""
        assert sample_user_list_response["limit"] > 0


# -- UserUpdateRequest structure ----------------------------------------------


class TestUserUpdateRequestStructure:
    """Validate UserUpdateRequest schema structure."""

    def test_all_fields_optional(self) -> None:
        """All update fields are optional (can create with empty dict)."""
        model = UserUpdateRequest()
        assert model.role is None
        assert model.tier is None
        assert model.is_active is None

    def test_role_only_update(self) -> None:
        """Can update role alone."""
        model = UserUpdateRequest(role="admin")
        assert model.role == "admin"
        assert model.tier is None
        assert model.is_active is None

    def test_tier_only_update(self) -> None:
        """Can update tier alone."""
        model = UserUpdateRequest(tier="pro")
        assert model.tier == "pro"
        assert model.role is None

    def test_is_active_only_update(self) -> None:
        """Can update is_active alone."""
        model = UserUpdateRequest(is_active=False)
        assert model.is_active is False

    def test_all_fields_update(self) -> None:
        """Can update all fields at once."""
        model = UserUpdateRequest(role="user", tier="pro", is_active=True)
        assert model.role == "user"
        assert model.tier == "pro"
        assert model.is_active is True

"""Golden tests for admin response structures.

Validates that admin-related data conforms to expected schemas:
- UserResponse: admin view of a user (id, email, role, tier, active, timestamps)
- SystemMetricsResponse: aggregate system metrics (users, artifacts, courses, pipeline, storage)
- UserListResponse: paginated user list envelope
- UserUpdateRequest: allowed update fields
"""

import pytest

from app.api.admin import (
    PipelineFailure,
    PipelineStageBreakdown,
    SubscriptionSection,
    SystemMetricsResponse,
    UserDetailResponse,
    UserListResponse,
    UserProfileSection,
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


# -- UserDetailResponse structure ----------------------------------------------

@pytest.fixture
def sample_user_profile():
    """A realistic user profile section."""
    return {
        "id": "user-001",
        "email": "alice@example.com",
        "username": "alice",
        "role": "user",
        "tier": "free",
        "is_active": True,
        "email_verified": True,
        "mfa_enabled": False,
        "avatar_url": None,
        "last_login_at": "2026-03-01T08:30:00",
        "created_at": "2026-01-15T10:00:00",
    }


@pytest.fixture
def sample_full_user_detail(sample_user_profile):
    """A complete user detail response with all sections."""
    return {
        "profile": sample_user_profile,
        "subscription": {
            "plan": "pro",
            "status": "active",
            "current_period_start": "2026-03-01T00:00:00",
            "current_period_end": "2026-04-01T00:00:00",
            "cancel_at_period_end": False,
        },
        "storage": {
            "total_bytes": 10485760,
            "total_mb": 10.0,
            "total_files": 15,
            "status_breakdown": {"processed": 12, "ingested": 3},
        },
        "usage": {
            "today": {"ai_calls": 5, "tokens_input": 2000, "tokens_output": 1000, "uploads": 2},
            "last_30_days": {"ai_calls": 100, "tokens_input": 50000, "tokens_output": 25000, "uploads": 20},
        },
        "pipeline": {
            "total_runs": 30,
            "success_count": 28,
            "failed_count": 2,
            "avg_duration_ms": 4500,
            "stages": [
                {"stage": "ingest", "total": 10, "success": 10, "failed": 0},
                {"stage": "classify", "total": 10, "success": 9, "failed": 1},
            ],
            "recent_failures": [
                {"stage": "classify", "error_message": "Timeout", "started_at": "2026-03-10T10:00:00"},
            ],
        },
        "study": {
            "total_sessions": 25,
            "cards_reviewed": 500,
            "quiz_questions_answered": 150,
            "quiz_correct": 120,
            "quiz_accuracy_pct": 80.0,
            "total_study_hours": 20.5,
        },
        "content": {
            "courses_count": 3,
            "artifacts_count": 15,
            "exams_count": 4,
            "per_course": [
                {"code": "CSIT302", "name": "Cybersecurity", "artifact_count": 8},
                {"code": "CSIT314", "name": "Software Dev", "artifact_count": 7},
            ],
        },
        "gamification": {"total_xp": 2500, "level": 7, "achievements_count": 12},
        "chat": {"total_sessions": 15, "total_messages": 80, "total_tokens": 40000},
    }


class TestUserDetailResponseStructure:
    """Validate UserDetailResponse schema structure."""

    def test_has_all_section_keys(self, sample_full_user_detail) -> None:
        """UserDetailResponse has all 9 section keys."""
        expected = {
            "profile", "subscription", "storage", "usage",
            "pipeline", "study", "content", "gamification", "chat",
        }
        assert set(sample_full_user_detail.keys()) == expected

    def test_pydantic_model_accepts_full_data(self, sample_full_user_detail) -> None:
        """UserDetailResponse Pydantic model accepts complete data."""
        model = UserDetailResponse(**sample_full_user_detail)
        assert model.profile.id == "user-001"
        assert model.subscription is not None
        assert model.subscription.plan == "pro"
        assert model.storage is not None
        assert model.storage.total_files == 15
        assert model.pipeline is not None
        assert model.pipeline.total_runs == 30

    def test_pydantic_model_accepts_null_sections(self, sample_user_profile) -> None:
        """UserDetailResponse accepts None for all optional sections."""
        data = {"profile": sample_user_profile}
        model = UserDetailResponse(**data)
        assert model.profile.id == "user-001"
        assert model.subscription is None
        assert model.storage is None
        assert model.usage is None
        assert model.pipeline is None
        assert model.study is None
        assert model.content is None
        assert model.gamification is None
        assert model.chat is None


class TestUserProfileSectionStructure:
    """Validate UserProfileSection schema."""

    def test_has_required_fields(self, sample_user_profile) -> None:
        """Profile has all required fields."""
        required = {
            "id", "email", "username", "role", "tier", "is_active",
            "email_verified", "mfa_enabled", "avatar_url",
            "last_login_at", "created_at",
        }
        missing = required - sample_user_profile.keys()
        assert not missing, f"Missing fields: {missing}"

    def test_pydantic_model_accepts_valid_data(self, sample_user_profile) -> None:
        """UserProfileSection Pydantic model works."""
        model = UserProfileSection(**sample_user_profile)
        assert model.email == "alice@example.com"
        assert model.email_verified is True
        assert model.mfa_enabled is False


class TestSubscriptionSectionStructure:
    """Validate SubscriptionSection schema."""

    def test_has_required_fields(self, sample_full_user_detail) -> None:
        """Subscription has all required fields."""
        sub = sample_full_user_detail["subscription"]
        required = {"plan", "status", "current_period_start", "current_period_end", "cancel_at_period_end"}
        missing = required - sub.keys()
        assert not missing, f"Missing fields: {missing}"

    def test_pydantic_model_accepts_valid_data(self, sample_full_user_detail) -> None:
        """SubscriptionSection Pydantic model works."""
        model = SubscriptionSection(**sample_full_user_detail["subscription"])
        assert model.plan == "pro"
        assert model.cancel_at_period_end is False


class TestStorageSectionStructure:
    """Validate StorageSection schema."""

    def test_has_required_fields(self, sample_full_user_detail) -> None:
        """Storage has all required fields."""
        storage = sample_full_user_detail["storage"]
        required = {"total_bytes", "total_mb", "total_files", "status_breakdown"}
        missing = required - storage.keys()
        assert not missing, f"Missing fields: {missing}"

    def test_status_breakdown_is_dict(self, sample_full_user_detail) -> None:
        """status_breakdown is a dict of string to int."""
        breakdown = sample_full_user_detail["storage"]["status_breakdown"]
        assert isinstance(breakdown, dict)
        for k, v in breakdown.items():
            assert isinstance(k, str)
            assert isinstance(v, int)


class TestPipelineSectionStructure:
    """Validate PipelineSection schema."""

    def test_has_required_fields(self, sample_full_user_detail) -> None:
        """Pipeline has all required fields."""
        pipeline = sample_full_user_detail["pipeline"]
        required = {"total_runs", "success_count", "failed_count", "avg_duration_ms", "stages", "recent_failures"}
        missing = required - pipeline.keys()
        assert not missing, f"Missing fields: {missing}"

    def test_stage_breakdown_structure(self, sample_full_user_detail) -> None:
        """Each stage entry has stage/total/success/failed."""
        for stage in sample_full_user_detail["pipeline"]["stages"]:
            model = PipelineStageBreakdown(**stage)
            assert model.stage
            assert model.total >= 0

    def test_failure_structure(self, sample_full_user_detail) -> None:
        """Each failure entry has stage/error_message/started_at."""
        for failure in sample_full_user_detail["pipeline"]["recent_failures"]:
            model = PipelineFailure(**failure)
            assert model.stage


class TestStudySectionStructure:
    """Validate StudySection schema."""

    def test_has_required_fields(self, sample_full_user_detail) -> None:
        """Study has all required fields."""
        study = sample_full_user_detail["study"]
        required = {
            "total_sessions", "cards_reviewed", "quiz_questions_answered",
            "quiz_correct", "quiz_accuracy_pct", "total_study_hours",
        }
        missing = required - study.keys()
        assert not missing, f"Missing fields: {missing}"

    def test_quiz_accuracy_is_percentage(self, sample_full_user_detail) -> None:
        """quiz_accuracy_pct is between 0 and 100."""
        pct = sample_full_user_detail["study"]["quiz_accuracy_pct"]
        assert 0 <= pct <= 100

"""Golden tests for multi-tenant structure validation."""

import pytest

from app.models.user_settings import UserSettings


class TestUserSettingsSchema:
    """Verify UserSettings model has expected columns."""

    def test_has_required_columns(self):
        """UserSettings model has all expected column names."""
        columns = {c.key for c in UserSettings.__table__.columns}
        expected = {"id", "user_id", "settings_json", "theme", "dashboard_layout", "created_at", "updated_at"}
        assert expected.issubset(columns), f"Missing columns: {expected - columns}"

    def test_user_id_is_unique(self):
        """user_id has a unique constraint (one settings row per user)."""
        user_id_col = UserSettings.__table__.columns["user_id"]
        assert user_id_col.unique is True or any(
            uc.columns.keys() == ["user_id"]
            for uc in UserSettings.__table__.constraints
            if hasattr(uc, "columns")
        )

    def test_theme_has_default(self):
        """theme column has a default value."""
        theme_col = UserSettings.__table__.columns["theme"]
        assert theme_col.default is not None


class TestAdminMetricsResponseStructure:
    """Verify admin metrics response schema has all expected fields."""

    def test_metrics_response_has_expected_fields(self):
        """SystemMetricsResponse schema includes all metric keys."""
        from app.api.admin import SystemMetricsResponse

        fields = set(SystemMetricsResponse.model_fields.keys())
        expected = {
            "total_users",
            "total_artifacts",
            "total_courses",
            "pipeline_runs_24h",
            "total_storage_bytes",
            "total_storage_mb",
        }
        assert expected == fields


class TestUserResponseStructure:
    """Verify admin user response schema."""

    def test_user_response_has_expected_fields(self):
        """UserResponse schema includes all user fields."""
        from app.api.admin import UserResponse

        fields = set(UserResponse.model_fields.keys())
        expected = {"id", "email", "username", "role", "tier", "is_active", "created_at", "last_login_at"}
        assert expected == fields

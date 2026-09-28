"""Golden tests for multi-tenant structure validation."""

from app.models.user_settings import UserSettings


class TestUserSettingsSchema:
    """Verify UserSettings model has expected columns."""

    def test_has_required_columns(self):
        """UserSettings model has all expected column names."""
        columns = {c.key for c in UserSettings.__table__.columns}
        expected = {
            "id",
            "user_id",
            "settings_json",
            "theme",
            "dashboard_layout",
            "created_at",
            "updated_at",
        }
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
            # Today's instance-wide AI spend against the configured ceiling.
            "ai_calls_today",
            "ai_tokens_today",
            "ai_calls_ceiling",
            "ai_tokens_ceiling",
        }
        assert expected == fields


class TestUserResponseStructure:
    """Verify admin user response schema."""

    #: The shape a list row and an update result share.
    BASE_FIELDS = {
        "id",
        "email",
        "username",
        "role",
        "tier",
        "is_active",
        # Whether TOTP is configured, so the admin UI can disable "Reset MFA"
        # for accounts with none instead of learning it from the response after
        # the click (GL#3). A boolean about setup — see the exclusion test below
        # for what must never join it.
        "mfa_enabled",
        "created_at",
        "last_login_at",
    }

    def test_user_response_has_expected_fields(self):
        """UserResponse schema includes all user fields."""
        from app.api.admin import UserResponse

        assert set(UserResponse.model_fields.keys()) == self.BASE_FIELDS

    def test_update_response_adds_only_sessions_revoked(self):
        """The PATCH result knows one thing a list row cannot (GL#3).

        `sessions_revoked` is deliberately *not* on `UserResponse`: listing users
        revokes nothing, so there the field could only ever be a meaningless
        `false` — a fact-shaped non-fact, which is worse than an absent one.
        """
        from app.api.admin import UserUpdateResponse

        assert set(UserUpdateResponse.model_fields.keys()) == self.BASE_FIELDS | {
            "sessions_revoked"
        }

    def test_no_admin_user_schema_carries_mfa_material(self):
        """`mfa_enabled` is a boolean about setup; the secret must not follow it.

        The scope line from GL#3, pinned: adding a convenient `mfa_secret` or
        `backup_codes` here would erode the exclusion `UserProfileResponse`
        already makes deliberately.
        """
        from app.api.admin import UserProfileSection, UserResponse, UserUpdateResponse

        forbidden = {"mfa_secret", "backup_codes", "hashed_password", "totp_secret"}
        for schema in (UserResponse, UserUpdateResponse, UserProfileSection):
            leaked = forbidden & set(schema.model_fields.keys())
            assert not leaked, f"{schema.__name__} exposes {leaked}"

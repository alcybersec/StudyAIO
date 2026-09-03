"""Tests for quota service.

Two layers are covered separately: per-tier limits (skipped in self-hosted mode
and for tiers configured as unlimited) and the instance-wide ceiling, which is
deliberately *not* skipped by either.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import GlobalCeilingError, QuotaExceededError
from app.services.quota_service import (
    PIPELINE_AI_CALLS_PER_UPLOAD,
    _limit_for,
    check_ai_quota,
    check_course_quota,
    check_global_ai_ceiling,
    check_upload_quota,
    get_course_count,
    get_monthly_upload_count,
    get_usage_today,
)


@pytest.fixture
def mock_session():
    """Create a mock async database session."""
    return AsyncMock()


def _settings(**overrides) -> SimpleNamespace:
    """Settings stand-in with the shipped defaults, overridable per test."""
    values = {
        "self_hosted": False,
        "free_max_courses": 1,
        "free_max_uploads_per_month": 5,
        "free_max_ai_calls_per_day": 100,
        "pro_max_courses": 0,
        "pro_max_uploads_per_month": 0,
        "pro_max_ai_calls_per_day": 0,
        "global_max_ai_calls_per_day": 0,
        "global_max_ai_tokens_per_day": 0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture
def quota_settings():
    """Patch quota_service.settings; yields a mutable namespace."""
    cfg = _settings()
    with patch("app.services.quota_service.settings", cfg):
        yield cfg


class TestLimitFor:
    """Limits come from config, and 0 means unlimited."""

    def test_free_and_pro_resolve_independently(self, quota_settings):
        quota_settings.free_max_courses = 3
        quota_settings.pro_max_courses = 50
        assert _limit_for("free", "courses") == 3
        assert _limit_for("pro", "courses") == 50

    def test_zero_means_unlimited(self, quota_settings):
        quota_settings.pro_max_ai_calls_per_day = 0
        assert _limit_for("pro", "ai_calls_per_day") == 0

    def test_unknown_tier_falls_back_to_free(self, quota_settings):
        quota_settings.free_max_courses = 7
        assert _limit_for("mystery", "courses") == 7

    def test_reads_the_current_setting(self, quota_settings):
        """Changing config must take effect without touching source."""
        quota_settings.free_max_uploads_per_month = 999
        assert _limit_for("free", "uploads_per_month") == 999


class TestGetUsageToday:
    @pytest.mark.asyncio
    async def test_returns_record(self, mock_session):
        record = MagicMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = record
        mock_session.execute.return_value = result

        assert await get_usage_today(mock_session, "user-1") is record

    @pytest.mark.asyncio
    async def test_returns_none(self, mock_session):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        assert await get_usage_today(mock_session, "user-1") is None


class TestCounts:
    @pytest.mark.asyncio
    async def test_monthly_upload_count(self, mock_session):
        result = MagicMock()
        result.scalar_one.return_value = 4
        mock_session.execute.return_value = result

        assert await get_monthly_upload_count(mock_session, "user-1") == 4

    @pytest.mark.asyncio
    async def test_course_count(self, mock_session):
        result = MagicMock()
        result.scalar_one.return_value = 2
        mock_session.execute.return_value = result

        assert await get_course_count(mock_session, "user-1") == 2


class TestCheckUploadQuota:
    @pytest.mark.asyncio
    async def test_self_hosted_bypasses(self, quota_settings, mock_session):
        quota_settings.self_hosted = True
        await check_upload_quota(mock_session, "user-1", "free")
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_pro_tier_bypasses(self, quota_settings, mock_session):
        """Pro is configured unlimited by default."""
        await check_upload_quota(mock_session, "user-1", "pro")
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_under_limit_passes(self, quota_settings, mock_session):
        result = MagicMock()
        result.scalar_one.return_value = 2
        mock_session.execute.return_value = result

        await check_upload_quota(mock_session, "user-1", "free")

    @pytest.mark.asyncio
    async def test_at_limit_raises(self, quota_settings, mock_session):
        result = MagicMock()
        result.scalar_one.return_value = quota_settings.free_max_uploads_per_month
        mock_session.execute.return_value = result

        with pytest.raises(QuotaExceededError, match="uploads"):
            await check_upload_quota(mock_session, "user-1", "free")

    @pytest.mark.asyncio
    async def test_configured_limit_is_honoured(self, quota_settings, mock_session):
        quota_settings.free_max_uploads_per_month = 50
        result = MagicMock()
        result.scalar_one.return_value = 20
        mock_session.execute.return_value = result

        await check_upload_quota(mock_session, "user-1", "free")


class TestCheckAiQuota:
    @pytest.mark.asyncio
    async def test_self_hosted_bypasses(self, quota_settings, mock_session):
        quota_settings.self_hosted = True
        await check_ai_quota(mock_session, "user-1", "free")
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_pro_tier_bypasses(self, quota_settings, mock_session):
        await check_ai_quota(mock_session, "user-1", "pro")
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_under_limit_passes(self, quota_settings, mock_session):
        usage = MagicMock()
        usage.ai_calls_count = 10
        result = MagicMock()
        result.scalar_one_or_none.return_value = usage
        mock_session.execute.return_value = result

        await check_ai_quota(mock_session, "user-1", "free")

    @pytest.mark.asyncio
    async def test_no_record_passes(self, quota_settings, mock_session):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        await check_ai_quota(mock_session, "user-1", "free")

    @pytest.mark.asyncio
    async def test_at_limit_raises(self, quota_settings, mock_session):
        usage = MagicMock()
        usage.ai_calls_count = quota_settings.free_max_ai_calls_per_day
        result = MagicMock()
        result.scalar_one_or_none.return_value = usage
        mock_session.execute.return_value = result

        with pytest.raises(QuotaExceededError, match="ai_calls"):
            await check_ai_quota(mock_session, "user-1", "free")

    @pytest.mark.asyncio
    async def test_reserves_the_whole_pipeline_run(self, quota_settings, mock_session):
        """An upload must be refused if the run cannot finish inside the quota.

        Otherwise a stage fails partway and leaves a half-processed artifact.
        """
        quota_settings.free_max_ai_calls_per_day = 10
        usage = MagicMock()
        usage.ai_calls_count = 8  # 8 + 4 > 10
        result = MagicMock()
        result.scalar_one_or_none.return_value = usage
        mock_session.execute.return_value = result

        with pytest.raises(QuotaExceededError, match="ai_calls"):
            await check_ai_quota(mock_session, "user-1", "free", calls=PIPELINE_AI_CALLS_PER_UPLOAD)

    @pytest.mark.asyncio
    async def test_exact_fit_is_allowed(self, quota_settings, mock_session):
        quota_settings.free_max_ai_calls_per_day = 10
        usage = MagicMock()
        usage.ai_calls_count = 6  # 6 + 4 == 10
        result = MagicMock()
        result.scalar_one_or_none.return_value = usage
        mock_session.execute.return_value = result

        await check_ai_quota(mock_session, "user-1", "free", calls=PIPELINE_AI_CALLS_PER_UPLOAD)


class TestCheckCourseQuota:
    @pytest.mark.asyncio
    async def test_self_hosted_bypasses(self, quota_settings, mock_session):
        quota_settings.self_hosted = True
        await check_course_quota(mock_session, "user-1", "free")
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_pro_tier_bypasses(self, quota_settings, mock_session):
        await check_course_quota(mock_session, "user-1", "pro")
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_under_limit_passes(self, quota_settings, mock_session):
        result = MagicMock()
        result.scalar_one.return_value = 0
        mock_session.execute.return_value = result

        await check_course_quota(mock_session, "user-1", "free")

    @pytest.mark.asyncio
    async def test_at_limit_raises(self, quota_settings, mock_session):
        result = MagicMock()
        result.scalar_one.return_value = quota_settings.free_max_courses
        mock_session.execute.return_value = result

        with pytest.raises(QuotaExceededError, match="courses"):
            await check_course_quota(mock_session, "user-1", "free")


class TestGlobalCeiling:
    """The operator's cost guard: applies where per-user quotas do not."""

    def _usage(self, mock_session, calls: int, tokens: int = 0) -> None:
        result = MagicMock()
        result.one.return_value = (calls, tokens)
        mock_session.execute.return_value = result

    @pytest.mark.asyncio
    async def test_disabled_by_default_costs_no_query(self, quota_settings, mock_session):
        await check_global_ai_ceiling(mock_session)
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_under_ceiling_passes(self, quota_settings, mock_session):
        quota_settings.global_max_ai_calls_per_day = 100
        self._usage(mock_session, calls=42)

        await check_global_ai_ceiling(mock_session)

    @pytest.mark.asyncio
    async def test_at_call_ceiling_raises(self, quota_settings, mock_session):
        quota_settings.global_max_ai_calls_per_day = 100
        self._usage(mock_session, calls=100)

        with pytest.raises(GlobalCeilingError, match="AI call"):
            await check_global_ai_ceiling(mock_session)

    @pytest.mark.asyncio
    async def test_at_token_ceiling_raises(self, quota_settings, mock_session):
        quota_settings.global_max_ai_tokens_per_day = 1000
        self._usage(mock_session, calls=1, tokens=1000)

        with pytest.raises(GlobalCeilingError, match="AI token"):
            await check_global_ai_ceiling(mock_session)

    @pytest.mark.asyncio
    async def test_carries_a_retry_after(self, quota_settings, mock_session):
        quota_settings.global_max_ai_calls_per_day = 1
        self._usage(mock_session, calls=1)

        with pytest.raises(GlobalCeilingError) as exc:
            await check_global_ai_ceiling(mock_session)

        assert 0 < exc.value.retry_after_seconds <= 86400

    @pytest.mark.asyncio
    async def test_applies_to_pro_tier(self, quota_settings, mock_session):
        """Per-user quotas skip pro; the cost guard must not."""
        quota_settings.global_max_ai_calls_per_day = 1
        self._usage(mock_session, calls=5)

        with pytest.raises(GlobalCeilingError):
            await check_ai_quota(mock_session, "user-1", "pro")

    @pytest.mark.asyncio
    async def test_applies_in_self_hosted_mode(self, quota_settings, mock_session):
        quota_settings.self_hosted = True
        quota_settings.global_max_ai_calls_per_day = 1
        self._usage(mock_session, calls=5)

        with pytest.raises(GlobalCeilingError):
            await check_ai_quota(mock_session, "user-1", "free")

    @pytest.mark.asyncio
    async def test_blocks_uploads_too(self, quota_settings, mock_session):
        quota_settings.global_max_ai_calls_per_day = 1
        self._usage(mock_session, calls=5)

        with pytest.raises(GlobalCeilingError):
            await check_upload_quota(mock_session, "user-1", "pro")

    @pytest.mark.asyncio
    async def test_course_creation_is_not_ai_spend(self, quota_settings, mock_session):
        """Creating a course makes no AI call, so the ceiling must not block it."""
        quota_settings.global_max_ai_calls_per_day = 1
        result = MagicMock()
        result.scalar_one.return_value = 0
        mock_session.execute.return_value = result

        await check_course_quota(mock_session, "user-1", "free")

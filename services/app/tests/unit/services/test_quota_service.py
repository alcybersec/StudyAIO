"""Tests for quota service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import QuotaExceededError
from app.services.quota_service import (
    FREE_MAX_AI_CALLS_PER_DAY,
    FREE_MAX_COURSES,
    FREE_MAX_UPLOADS_PER_MONTH,
    check_ai_quota,
    check_course_quota,
    check_upload_quota,
    get_course_count,
    get_monthly_upload_count,
    get_usage_today,
)


@pytest.fixture
def mock_session():
    """Create a mock async database session."""
    return AsyncMock()


class TestGetUsageToday:
    """Tests for get_usage_today."""

    @pytest.mark.asyncio
    async def test_returns_record(self, mock_session):
        """Returns usage record when found."""
        record = MagicMock()
        record.ai_calls_count = 5
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = record
        mock_session.execute.return_value = mock_result

        result = await get_usage_today(mock_session, "user-1")
        assert result == record

    @pytest.mark.asyncio
    async def test_returns_none(self, mock_session):
        """Returns None when no record exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await get_usage_today(mock_session, "user-1")
        assert result is None


class TestGetMonthlyUploadCount:
    """Tests for get_monthly_upload_count."""

    @pytest.mark.asyncio
    async def test_returns_count(self, mock_session):
        """Returns monthly upload count."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 3
        mock_session.execute.return_value = mock_result

        result = await get_monthly_upload_count(mock_session, "user-1")
        assert result == 3


class TestGetCourseCount:
    """Tests for get_course_count."""

    @pytest.mark.asyncio
    async def test_returns_count(self, mock_session):
        """Returns course count."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 1
        mock_session.execute.return_value = mock_result

        result = await get_course_count(mock_session, "user-1")
        assert result == 1


class TestCheckUploadQuota:
    """Tests for check_upload_quota."""

    @pytest.mark.asyncio
    @patch("app.services.quota_service.settings")
    async def test_self_hosted_bypasses(self, mock_settings, mock_session):
        """Self-hosted mode skips quota check."""
        mock_settings.self_hosted = True
        await check_upload_quota(mock_session, "user-1", "free")
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.quota_service.settings")
    async def test_pro_tier_bypasses(self, mock_settings, mock_session):
        """Pro tier users have unlimited uploads."""
        mock_settings.self_hosted = False
        await check_upload_quota(mock_session, "user-1", "pro")
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.quota_service.settings")
    async def test_under_limit_passes(self, mock_settings, mock_session):
        """Free user under limit can upload."""
        mock_settings.self_hosted = False
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 2
        mock_session.execute.return_value = mock_result

        await check_upload_quota(mock_session, "user-1", "free")

    @pytest.mark.asyncio
    @patch("app.services.quota_service.settings")
    async def test_at_limit_raises(self, mock_settings, mock_session):
        """Free user at limit gets QuotaExceededError."""
        mock_settings.self_hosted = False
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = FREE_MAX_UPLOADS_PER_MONTH
        mock_session.execute.return_value = mock_result

        with pytest.raises(QuotaExceededError, match="uploads"):
            await check_upload_quota(mock_session, "user-1", "free")


class TestCheckAiQuota:
    """Tests for check_ai_quota."""

    @pytest.mark.asyncio
    @patch("app.services.quota_service.settings")
    async def test_self_hosted_bypasses(self, mock_settings, mock_session):
        """Self-hosted mode skips AI quota check."""
        mock_settings.self_hosted = True
        await check_ai_quota(mock_session, "user-1", "free")
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.quota_service.settings")
    async def test_pro_tier_bypasses(self, mock_settings, mock_session):
        """Pro tier users have unlimited AI calls."""
        mock_settings.self_hosted = False
        await check_ai_quota(mock_session, "user-1", "pro")
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.quota_service.settings")
    async def test_under_limit_passes(self, mock_settings, mock_session):
        """Free user under AI limit can call."""
        mock_settings.self_hosted = False
        usage = MagicMock()
        usage.ai_calls_count = 10
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = usage
        mock_session.execute.return_value = mock_result

        await check_ai_quota(mock_session, "user-1", "free")

    @pytest.mark.asyncio
    @patch("app.services.quota_service.settings")
    async def test_no_record_passes(self, mock_settings, mock_session):
        """Free user with no usage record can call."""
        mock_settings.self_hosted = False
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await check_ai_quota(mock_session, "user-1", "free")

    @pytest.mark.asyncio
    @patch("app.services.quota_service.settings")
    async def test_at_limit_raises(self, mock_settings, mock_session):
        """Free user at AI call limit gets QuotaExceededError."""
        mock_settings.self_hosted = False
        usage = MagicMock()
        usage.ai_calls_count = FREE_MAX_AI_CALLS_PER_DAY
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = usage
        mock_session.execute.return_value = mock_result

        with pytest.raises(QuotaExceededError, match="ai_calls"):
            await check_ai_quota(mock_session, "user-1", "free")


class TestCheckCourseQuota:
    """Tests for check_course_quota."""

    @pytest.mark.asyncio
    @patch("app.services.quota_service.settings")
    async def test_self_hosted_bypasses(self, mock_settings, mock_session):
        """Self-hosted mode skips course quota check."""
        mock_settings.self_hosted = True
        await check_course_quota(mock_session, "user-1", "free")
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.quota_service.settings")
    async def test_pro_tier_bypasses(self, mock_settings, mock_session):
        """Pro tier users have unlimited courses."""
        mock_settings.self_hosted = False
        await check_course_quota(mock_session, "user-1", "pro")
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.quota_service.settings")
    async def test_under_limit_passes(self, mock_settings, mock_session):
        """Free user with 0 courses can create one."""
        mock_settings.self_hosted = False
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 0
        mock_session.execute.return_value = mock_result

        await check_course_quota(mock_session, "user-1", "free")

    @pytest.mark.asyncio
    @patch("app.services.quota_service.settings")
    async def test_at_limit_raises(self, mock_settings, mock_session):
        """Free user at course limit gets QuotaExceededError."""
        mock_settings.self_hosted = False
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = FREE_MAX_COURSES
        mock_session.execute.return_value = mock_result

        with pytest.raises(QuotaExceededError, match="courses"):
            await check_course_quota(mock_session, "user-1", "free")

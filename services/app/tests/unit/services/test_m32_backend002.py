"""M32-S1-BACKEND-002: regression tests for four functional bugs (R-016)."""

import re
from pathlib import Path

from app.api import billing

APP = Path(__file__).resolve().parents[3] / "app"


class TestBillingLimits:
    def test_free_limits_come_from_settings(self):
        assert billing._limit_or_none("free", "courses") == 1
        assert billing._limit_or_none("free", "ai_calls_per_day") == 100

    def test_zero_means_unlimited_none(self):
        assert billing._limit_or_none("pro", "courses") is None

    def test_no_stale_free_max_constants(self):
        assert "quota_service.FREE_MAX" not in (APP / "api/billing.py").read_text()


class TestGcalTimeMin:
    def test_time_min_is_not_double_suffixed(self):
        src = (APP / "services/gcal_service.py").read_text()
        assert not re.search(r'isoformat\(\)\s*\+\s*"Z"', src)


class TestAchievementNotification:
    def test_uses_title_column_and_logs_at_error(self):
        src = (APP / "services/achievement_service.py").read_text()
        assert "achievement.name" not in src
        assert "achievement.title" in src
        assert 'logger.error(\n                    "achievement_inbox_notification_failed"' in src


class TestMfaDisableMapping:
    def test_value_error_mapped_to_400(self):
        src = (APP / "api/auth.py").read_text()
        block = src.split("async def mfa_disable")[1].split("@router")[0]
        assert "except ValueError" in block and "status_code=400" in block

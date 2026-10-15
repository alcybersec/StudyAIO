"""Retention split by "has a study plan" (ADR 0007 Decision 9; the M33 gate metric)."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

from app.services import usage_service as svc


def test_weak_spot_events_are_allowlisted_and_properties_fit():
    assert {"study_plan_built", "targeted_generation_requested"} <= svc.USAGE_EVENTS
    assert {"count", "week", "duration_seconds"} <= svc.ALLOWED_PROPERTY_KEYS
    assert svc._valid_properties({"count": 5, "week": 3})
    assert svc._valid_properties({"count": 8, "duration_seconds": 1500})


class TestBuildPlanSplit:
    def test_each_cohort_has_both_arms(self):
        signups = {(date(2026, 9, 28), True): 3, (date(2026, 9, 28), False): 7}
        active = {
            (date(2026, 9, 28), True): {7: 2, 30: 1},
            (date(2026, 9, 28), False): {7: 1, 30: 0},
        }
        out = svc.build_plan_split(signups, active, today=date(2026, 11, 30))
        assert out == [
            {
                "week_start": "2026-09-28",
                "with_plan": {"signups": 3, "d7": 2, "d30": 1},
                "without_plan": {"signups": 7, "d7": 1, "d30": 0},
            }
        ]

    def test_missing_arm_is_zero_signups(self):
        out = svc.build_plan_split({(date(2026, 9, 28), False): 4}, {}, today=date(2026, 11, 30))
        assert out[0]["with_plan"] == {"signups": 0, "d7": 0, "d30": 0}

    def test_checkpoints_not_yet_reached_are_null(self):
        out = svc.build_plan_split({(date(2026, 10, 5), True): 1}, {}, today=date(2026, 10, 11))
        assert out[0]["with_plan"]["d7"] is None and out[0]["with_plan"]["d30"] is None

    def test_oldest_cohort_first(self):
        signups = {(date(2026, 10, 5), True): 1, (date(2026, 9, 28), True): 1}
        out = svc.build_plan_split(signups, {}, today=date(2026, 12, 1))
        assert [r["week_start"] for r in out] == ["2026-09-28", "2026-10-05"]


class TestReadoutQueries:
    async def test_split_is_computed_from_study_plans_and_excludes_admin_demo(self):
        session = AsyncMock()
        result = MagicMock()
        result.all.return_value = []
        session.execute.return_value = result
        out = await svc.retention_readout(session, weeks=8)
        assert out["plan_split"] == []
        calls = session.execute.await_args_list
        sql = " ".join(str(c.args[0].compile()) for c in calls)
        assert "study_plans" in sql
        flat = str([p for c in calls for p in c.args[0].compile().params.values()])
        assert "admin" in flat and "demo" in flat

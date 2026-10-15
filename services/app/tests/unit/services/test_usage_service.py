"""Usage events: allowlists, never-raising record, cohort math (GL#37)."""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.usage_event import UsageEvent
from app.services import usage_service as svc

USER = "user-1"


def _session():
    session = AsyncMock()
    session.add = MagicMock()
    savepoint = MagicMock()
    savepoint.__aenter__ = AsyncMock(return_value=None)
    savepoint.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested = MagicMock(return_value=savepoint)
    return session


class TestRecord:
    async def test_records_an_allowed_event(self):
        session = _session()
        ok = await svc.record(
            session, USER, "flashcard_reviewed", course_id="c-1", properties={"quality": 4}
        )
        assert ok is True
        event = session.add.call_args.args[0]
        assert isinstance(event, UsageEvent)
        assert (event.user_id, event.event, event.course_id) == (USER, "flashcard_reviewed", "c-1")
        assert event.properties == {"quality": 4}

    async def test_properties_default_to_empty(self):
        session = _session()
        await svc.record(session, USER, "summary_viewed")
        assert session.add.call_args.args[0].properties == {}

    async def test_unknown_event_is_dropped_not_raised(self):
        session = _session()
        assert await svc.record(session, USER, "page_hover") is False
        session.add.assert_not_called()

    @pytest.mark.parametrize(
        "props",
        [
            {"email": "a@b.c"},  # key not allowlisted
            {"week": "free text with spaces"},  # free text
            {"week": "x" * 41},  # too long
            {"week": {"nested": 1}},  # not scalar
            {"week": [1, 2]},
            {"week": None},
            {
                "week": 1,
                "count": 1,
                "correct": 1,
                "quality": 1,
                "is_correct": True,
                "duration_seconds": 1,
                "rating": 1,
            },  # 7 allowed keys: over the cap
        ],
    )
    async def test_bad_properties_are_dropped(self, props):
        session = _session()
        assert await svc.record(session, USER, "quiz_answered", properties=props) is False
        session.add.assert_not_called()

    async def test_scalar_tokens_accepted(self):
        session = _session()
        ok = await svc.record(
            session,
            USER,
            "quiz_answered",
            properties={"is_correct": True, "week": 3, "target_type": "quiz_question"},
        )
        assert ok is True

    async def test_database_failure_never_raises(self):
        session = _session()
        session.flush.side_effect = RuntimeError("db down")
        assert await svc.record(session, USER, "summary_viewed") is False

    async def test_runs_inside_a_savepoint(self):
        session = _session()
        await svc.record(session, USER, "summary_viewed")
        session.begin_nested.assert_called_once()

    def test_client_events_are_view_events_only(self):
        assert frozenset({"summary_viewed", "study_plan_viewed"}) == svc.CLIENT_EVENTS
        assert svc.CLIENT_EVENTS <= svc.USAGE_EVENTS


class TestCohorts:
    """Fixed data: weeks start Monday, dN is a calendar-day offset from signup."""

    def test_cohort_math(self):
        signups = [(date(2026, 9, 28), 4), (date(2026, 10, 5), 2)]
        active = {
            date(2026, 9, 28): {1: 3, 7: 2, 30: 0},
            date(2026, 10, 5): {1: 1, 7: 1, 30: 0},
        }
        out = svc.build_cohorts(signups, active, today=date(2026, 10, 11))
        by_week = {c["week_start"]: c for c in out}
        old = by_week["2026-09-28"]
        assert (old["signups"], old["d1"], old["d7"]) == (4, 3, 2)
        # 30 days have not elapsed since the cohort's last possible signup: unknown, not zero.
        assert old["d30"] is None
        young = by_week["2026-10-05"]
        assert young["d1"] == 1
        # Last possible signup 10-11; day 7 after it is 10-18 > today.
        assert young["d7"] is None

    def test_mature_cohort_reports_zero_not_null(self):
        out = svc.build_cohorts([(date(2026, 8, 3), 5)], {}, today=date(2026, 10, 11))
        assert (out[0]["d1"], out[0]["d7"], out[0]["d30"]) == (0, 0, 0)

    def test_cohorts_sorted_oldest_first(self):
        out = svc.build_cohorts(
            [(date(2026, 10, 5), 1), (date(2026, 9, 28), 1)], {}, today=date(2026, 10, 11)
        )
        assert [c["week_start"] for c in out] == ["2026-09-28", "2026-10-05"]

    def test_week_start_is_monday(self):
        assert svc.week_start(datetime(2026, 10, 11, 23, 0, tzinfo=UTC)) == date(2026, 10, 5)
        assert svc.week_start(datetime(2026, 10, 5, 0, 0, tzinfo=UTC)) == date(2026, 10, 5)


class TestRetentionQueries:
    async def test_excludes_admin_and_demo(self):
        session = AsyncMock()
        result = MagicMock()
        result.all.return_value = []
        session.execute.return_value = result
        out = await svc.retention_readout(session, weeks=8)
        assert out == {"cohorts": [], "features": [], "plan_split": []}
        sql = " ".join(str(c.args[0].compile()) for c in session.execute.await_args_list)
        assert "users.role" in sql
        params = []
        for c in session.execute.await_args_list:
            params.extend(c.args[0].compile().params.values())
        flat = str(params)
        assert "admin" in flat and "demo" in flat

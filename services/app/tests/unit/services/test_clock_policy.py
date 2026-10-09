"""R-023 clock policy: every converted service picks the policy-correct day.

Two frozen instants where the user's local date differs from the UTC date:

* ``AHEAD``  2026-03-10 23:30Z  -> Pacific/Kiritimati (+14) is already 03-11
* ``BEHIND`` 2026-03-10 02:00Z  -> America/Los_Angeles (-7, DST) is still 03-09

User-facing "today" follows the user's zone; quota, billing and admin stats
stay on the UTC day.
"""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core import clock
from app.services import (
    achievement_service,
    analytics_service,
    billing_service,
    calendar_service,
    challenge_service,
    courseops_service,
    exam_service,
    quota_service,
    schedule_service,
    srs_service,
    streak_service,
    study_service,
)

AHEAD = datetime(2026, 3, 10, 23, 30, tzinfo=UTC)
BEHIND = datetime(2026, 3, 10, 2, 0, tzinfo=UTC)
KIRI = "Pacific/Kiritimati"
LA = "America/Los_Angeles"
UTC_DAY = date(2026, 3, 10)


@pytest.fixture
def freeze(monkeypatch: pytest.MonkeyPatch):
    def _freeze(moment: datetime) -> None:
        monkeypatch.setattr(clock, "utc_now", lambda: moment)

    return _freeze


def _result(**attrs) -> MagicMock:
    r = MagicMock()
    for k, v in attrs.items():
        getattr(r, k).return_value = v
    return r


def _params(stmt) -> list:
    return list(stmt.compile().params.values())


class TestStreaks:
    @pytest.mark.asyncio
    async def test_session_is_recorded_on_the_users_local_day(self, freeze):
        freeze(AHEAD)
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_result(scalar_one_or_none=None))
        session.add = MagicMock()
        study = await streak_service.record_study_session(
            session, "c1", 1, 0, 0, 60, user_id="u1", tz=KIRI
        )
        assert study.session_date == date(2026, 3, 11)

    @pytest.mark.asyncio
    async def test_session_without_zone_uses_utc_day(self, freeze):
        freeze(AHEAD)
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_result(scalar_one_or_none=None))
        session.add = MagicMock()
        study = await streak_service.record_study_session(session, "c1", 1, 0, 0, 60, user_id="u1")
        assert study.session_date == UTC_DAY

    @pytest.mark.asyncio
    async def test_session_behind_utc_lands_on_previous_local_day(self, freeze):
        freeze(BEHIND)
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_result(scalar_one_or_none=None))
        session.add = MagicMock()
        study = await streak_service.record_study_session(
            session, "c1", 1, 0, 0, 60, user_id="u1", tz=LA
        )
        assert study.session_date == date(2026, 3, 9)

    @pytest.mark.asyncio
    async def test_streak_alive_when_last_study_is_local_today(self, freeze):
        freeze(AHEAD)
        session = AsyncMock()
        rows = MagicMock()
        rows.all.return_value = [(date(2026, 3, 11),), (date(2026, 3, 10),)]
        session.execute = AsyncMock(return_value=rows)
        local = await streak_service.get_streak(session, user_id="u1", tz=KIRI)
        utc = await streak_service.get_streak(session, user_id="u1")
        assert local["current_streak"] == 2
        # In UTC, 03-11 is tomorrow: the run is not anchored to today or yesterday.
        assert utc["current_streak"] == 0

    @pytest.mark.asyncio
    async def test_history_window_starts_from_local_today(self, freeze):
        freeze(AHEAD)
        session = AsyncMock()
        rows = MagicMock()
        rows.all.return_value = []
        session.execute = AsyncMock(return_value=rows)
        await streak_service.get_study_history(session, days=30, user_id="u1", tz=KIRI)
        assert date(2026, 2, 9) in _params(session.execute.await_args.args[0])  # 03-11 minus 30


class TestAnalytics:
    @pytest.mark.asyncio
    async def test_heatmap_ends_on_local_today(self, freeze):
        freeze(AHEAD)
        session = AsyncMock()
        session.execute = AsyncMock(return_value=iter([]))
        local = await analytics_service.get_study_heatmap(session, "u1", days=7, tz=KIRI)
        session.execute = AsyncMock(return_value=iter([]))
        utc = await analytics_service.get_study_heatmap(session, "u1", days=7)
        assert local[-1]["date"] == "2026-03-11"
        assert utc[-1]["date"] == "2026-03-10"

    @pytest.mark.asyncio
    async def test_snapshot_is_dated_by_the_local_day(self, freeze):
        freeze(AHEAD)
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_result(scalar_one_or_none=None))
        session.add = MagicMock()
        with patch.object(analytics_service, "get_overview", AsyncMock(return_value={})):
            snap = await analytics_service.compute_and_store_snapshot(session, "u1", tz=KIRI)
        assert snap.snapshot_date == date(2026, 3, 11)


class TestStudyPlans:
    @pytest.mark.asyncio
    async def test_week_plan_starts_on_local_today(self, freeze):
        freeze(AHEAD)
        with patch.object(exam_service, "list_exams", AsyncMock(return_value=[])):
            plan = await study_service.build_week_plan(AsyncMock(), "u1", tz=KIRI)
            utc_plan = await study_service.build_week_plan(AsyncMock(), "u1")
        assert plan[0]["day"] == "2026-03-11"
        assert utc_plan[0]["day"] == "2026-03-10"

    @pytest.mark.asyncio
    async def test_schedule_counts_down_in_the_users_local_days(self, freeze):
        freeze(AHEAD)
        exam = MagicMock()
        exam.course_id = "c1"
        exam.weeks_scope = [1]
        # 03-12 00:30Z is 03-12 14:30 in Kiritimati: one local day away from 03-11
        exam.exam_date = datetime(2026, 3, 12, 0, 30, tzinfo=UTC)
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[_result(scalar_one_or_none=exam), _result(scalar=0)]
        )
        with patch.object(schedule_service, "get_weak_topics", AsyncMock(return_value=[])):
            sched = await schedule_service.generate_study_schedule(
                session, "e1", days_ahead=2, user_id="u1", tz=KIRI
            )
        assert [d["date"] for d in sched] == ["2026-03-11", "2026-03-12"]
        assert [d["days_until_exam"] for d in sched] == [1, 0]

    def test_exam_countdown_uses_local_calendar_days(self, freeze):
        freeze(AHEAD)
        exam_date = datetime(2026, 3, 12, 0, 30, tzinfo=UTC)
        assert exam_service.days_until(exam_date, KIRI) == 1
        assert exam_service.days_until(exam_date, None) == 2

    def test_exam_countdown_never_negative(self, freeze):
        freeze(AHEAD)
        assert exam_service.days_until(datetime(2026, 3, 1, tzinfo=UTC), KIRI) == 0


class TestChallenges:
    @pytest.mark.asyncio
    async def test_daily_challenge_is_selected_for_the_local_day(self, freeze):
        freeze(AHEAD)
        session = AsyncMock()
        existing = MagicMock()
        session.execute = AsyncMock(return_value=_result(scalar_one_or_none=existing))
        await challenge_service.get_or_create_daily_challenge(session, tz=KIRI)
        assert date(2026, 3, 11) in _params(session.execute.await_args.args[0])

    @pytest.mark.asyncio
    async def test_progress_update_targets_the_local_day_challenge(self, freeze):
        freeze(AHEAD)
        with patch.object(
            challenge_service,
            "get_or_create_daily_challenge",
            AsyncMock(return_value=MagicMock(challenge_type="other")),
        ) as getter:
            await challenge_service.update_challenge_progress(
                AsyncMock(), "u1", "review_cards", tz=KIRI
            )
        assert getter.await_args.kwargs["tz"] == KIRI


class TestAchievements:
    @pytest.mark.asyncio
    async def test_streak_criteria_is_evaluated_in_the_users_zone(self):
        with patch("app.services.streak_service.get_streak", AsyncMock()) as streak:
            streak.return_value = {"current_streak": 5}
            ok = await achievement_service._evaluate_criteria(
                AsyncMock(), "u1", {"type": "streak", "threshold": 3}, KIRI
            )
        assert ok
        assert streak.await_args.kwargs["tz"] == KIRI


class TestCourseOps:
    @pytest.mark.asyncio
    async def test_upcoming_deadlines_cut_off_at_local_today(self, freeze):
        freeze(AHEAD)
        session = AsyncMock()
        rows = MagicMock()
        rows.all.return_value = []
        session.execute = AsyncMock(return_value=rows)
        await courseops_service.get_upcoming_deadlines_all_courses(session, user_id="u1", tz=KIRI)
        assert date(2026, 3, 11) in _params(session.execute.await_args.args[0])

    @pytest.mark.asyncio
    async def test_list_deadlines_upcoming_cut_off_at_local_today(self, freeze):
        freeze(AHEAD)
        session = AsyncMock()
        rows = MagicMock()
        rows.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=rows)
        with patch(
            "app.services.courseops_service.course_service.get_course_by_code",
            AsyncMock(return_value=MagicMock(id="c1")),
        ):
            await courseops_service.list_deadlines(
                session, "X", upcoming_only=True, user_id="u1", tz=KIRI
            )
        assert date(2026, 3, 11) in _params(session.execute.await_args.args[0])

    @pytest.mark.asyncio
    async def test_task_plan_is_stamped_with_the_local_day(self, freeze):
        freeze(AHEAD)
        session = AsyncMock()
        rows = MagicMock()
        rows.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=rows)
        course = MagicMock(name_="x")
        course.name = None
        course.term = None
        with patch(
            "app.services.calendar_service.course_service.get_course_by_code",
            AsyncMock(return_value=course),
        ):
            buf, _ = await calendar_service.generate_task_plan_md(
                session, "X", user_id="u1", tz=KIRI
            )
        assert "*Generated 2026-03-11 by StudyAIO*" in buf.getvalue().decode()


class TestUtcDayServices:
    """Quota, billing and admin stats ignore the user's zone: they use the UTC day."""

    @pytest.mark.asyncio
    async def test_quota_usage_is_read_for_the_utc_day(self, freeze):
        freeze(AHEAD)
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_result(scalar_one_or_none=None))
        await quota_service.get_usage_today(session, "u1")
        assert UTC_DAY in _params(session.execute.await_args.args[0])

    @pytest.mark.asyncio
    async def test_billing_usage_is_recorded_on_the_utc_day(self, freeze):
        freeze(AHEAD)
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_result(scalar_one_or_none=None))
        session.add = MagicMock()
        await billing_service.record_usage(session, "u1", ai_calls=1)
        assert session.add.call_args.args[0].record_date == UTC_DAY

    @pytest.mark.asyncio
    async def test_monthly_upload_window_is_utc_month(self, freeze):
        # 2026-03-31 23:30Z is already April in Kiritimati; quota stays in March.
        freeze(datetime(2026, 3, 31, 23, 30, tzinfo=UTC))
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_result(scalar_one=0))
        await quota_service.get_monthly_upload_count(session, "u1")
        assert date(2026, 3, 1) in _params(session.execute.await_args.args[0])


class TestDueToday:
    @pytest.mark.asyncio
    async def test_card_due_later_today_locally_counts_as_due(self, freeze):
        freeze(AHEAD)  # Kiritimati: 03-11 13:30; its day ends 2026-03-11T10:00Z
        session = AsyncMock()
        total = _result(scalar=2)
        rows = MagicMock()
        rows.all.return_value = [
            ("f1", 1, datetime(2026, 3, 11, 5, 0, tzinfo=UTC)),
            ("f2", 1, datetime(2026, 3, 11, 11, 0, tzinfo=UTC)),
        ]
        session.execute = AsyncMock(side_effect=[total, rows])
        stats = await srs_service.get_study_stats(session, user_id="u1", tz=KIRI)
        assert stats.due_today == 1

    @pytest.mark.asyncio
    async def test_due_cards_cutoff_is_end_of_local_day(self, freeze):
        freeze(AHEAD)
        session = AsyncMock()
        res = MagicMock()
        res.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=res)
        await srs_service.get_due_cards(session, user_id="u1", tz=KIRI)
        assert datetime(2026, 3, 11, 10, 0, tzinfo=UTC) in _params(
            session.execute.await_args.args[0]
        )

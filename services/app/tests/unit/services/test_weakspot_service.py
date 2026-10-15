"""weakspot_service (ADR 0007): ranking, dedup, focus choice, plan budget, targeted request."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import (
    GlobalCeilingError,
    QuotaExceededError,
    TargetedDailyCapError,
    TargetedUnitNotFoundError,
)
from app.services import weakspot_service as svc

USER = "user-1"


def _detail(
    code="C1",
    week=1,
    *,
    status="weak",
    weakness=0.5,
    priority=0.5,
    days=None,
    course_id="c-1",
    urgency=0.0,
):
    score = svc.WeekScore(
        status=status,
        weakness=weakness,
        confidence=0.5,
        urgency=urgency,
        priority=priority,
        evidence=5,
    )
    spot = svc.WeekWeakSpot(
        course_id=course_id,
        course_code=code,
        week=week,
        score=score,
        exam_id="e-1" if days is not None else None,
        days_to_exam=days,
    )
    summary = svc.WeekEvidenceSummary(
        quiz_attempts=5, quiz_accuracy=0.5, cards_reviewed=0, avg_ease=None,
        lapsed_cards=0, overdue_cards=0,
    )  # fmt: skip
    return svc.WeakSpotDetail(spot=spot, summary=summary)


class TestRanking:
    def test_higher_priority_first(self):
        a, b = _detail(week=1, priority=0.3), _detail(week=2, priority=0.9)
        assert svc.rank_spots([a, b]) == [b, a]

    def test_tie_breaks_by_weakness_then_exam_then_code_then_week(self):
        base = {"priority": 0.5}
        weaker = _detail("B", 3, weakness=0.7, **base)
        sooner = _detail("B", 2, weakness=0.5, days=2, **base)
        later = _detail("B", 1, weakness=0.5, days=9, **base)
        none = _detail("A", 9, weakness=0.5, **base)
        code_a = _detail("A", 8, weakness=0.5, days=9, **base)
        ranked = svc.rank_spots([none, later, code_a, sooner, weaker])
        assert ranked == [weaker, sooner, code_a, later, none]

    def test_unknown_sorts_after_scored_units(self):
        unknown = _detail(status="unknown", weakness=None, priority=0.0)
        solid = _detail(week=2, status="solid", weakness=0.1, priority=0.1)
        assert svc.rank_spots([unknown, solid]) == [solid, unknown]

    def test_order_is_independent_of_input_order(self):
        items = [_detail(week=w, priority=0.5) for w in range(1, 6)]
        assert svc.rank_spots(items) == svc.rank_spots(list(reversed(items)))


class TestDuplicate:
    def test_jaccard_at_threshold_is_duplicate(self):
        base = "one two three four five six seven eight"
        assert svc.is_duplicate(base + " nine", [base + " ten"]) is True  # 8/10 == 0.8
        assert svc.is_duplicate(base, [base + " nine"]) is True  # 8/9
        assert svc.is_duplicate(base + " nine ten", [base + " eleven"]) is False  # 8/11

    def test_below_threshold_is_not_duplicate(self):
        assert not svc.is_duplicate("alpha beta gamma delta", ["alpha beta epsilon zeta"])

    def test_empty_candidate_is_never_duplicate(self):
        assert not svc.is_duplicate("   ?!  ", ["", "!!"])


class TestClampMinutes:
    @pytest.mark.parametrize(("given", "want"), [(1, 10), (25, 25), (500, 90), (None, 25)])
    def test_clamped(self, given, want):
        assert svc.clamp_minutes(given) == want


class TestChooseFocus:
    def test_top_three_weak_or_shaky_only(self):
        spots = [_detail(week=w, status="weak", priority=1 - w / 10) for w in range(1, 4)]
        spots.append(_detail(week=4, status="shaky", priority=0.1))
        spots.append(_detail(week=5, status="solid", priority=0.05))
        focus, diag = svc.choose_focus(svc.rank_spots(spots), {("c-1", 5)})
        assert [d.spot.week for d in focus] == [1, 2, 3]
        assert diag is None  # three focus weeks and no imminent exam

    def test_diagnostic_added_when_fewer_than_three_focus(self):
        weak = _detail(week=1)
        unk = _detail(week=2, status="unknown", weakness=None, priority=0.0)
        focus, diag = svc.choose_focus(svc.rank_spots([weak, unk]), {("c-1", 2)})
        assert focus == [weak] and diag == unk

    def test_diagnostic_needs_an_active_question(self):
        unk = _detail(week=2, status="unknown", weakness=None, priority=0.0)
        assert svc.choose_focus([unk], set())[1] is None

    def test_urgent_unknown_joins_a_full_focus_list(self):
        spots = [_detail(week=w, priority=1 - w / 10) for w in range(1, 4)]
        calm = _detail(week=7, status="unknown", weakness=None, priority=0.0, urgency=0.2)
        urgent = _detail(week=8, status="unknown", weakness=None, priority=0.0, urgency=0.6)
        quiz_units = {("c-1", 7), ("c-1", 8)}
        _, diag = svc.choose_focus(svc.rank_spots([*spots, calm, urgent]), quiz_units)
        assert diag == urgent
        _, diag = svc.choose_focus(svc.rank_spots([*spots, calm]), quiz_units)
        assert diag is None

    def test_highest_urgency_unknown_is_the_diagnostic(self):
        a = _detail(week=2, status="unknown", weakness=None, priority=0.0, urgency=0.3)
        b = _detail(week=3, status="unknown", weakness=None, priority=0.0, urgency=0.4)
        _, diag = svc.choose_focus(svc.rank_spots([a, b]), {("c-1", 2), ("c-1", 3)})
        assert diag == b


def _cand(kind, n, reason):
    return svc.PlanCandidate(
        item_type=kind, item_id=f"{kind}{n}", course_id="c-1", course_code="C1", week=1,
        reason=reason,
    )  # fmt: skip


def _many(kind, count, reason):
    return [_cand(kind, i, reason) for i in range(count)]


def _minutes(items):
    return sum(i["minutes"] for i in items)


class TestSelectPlanItems:
    def test_default_budget_split_around_the_diagnostic(self):
        items = svc.select_plan_items(
            minutes=25,
            diagnostic=_many("quiz", 3, "diagnostic"),
            review=_many("card", 30, "review"),
            practice=_many("quiz", 30, "missed"),
        )
        assert _minutes(items) == 25
        assert [i["reason"] for i in items[:3]] == ["diagnostic"] * 3
        cards = [i for i in items if i["item_type"] == "card"]
        practice = [i for i in items if i["reason"] == "missed"]
        # 16 min left: 8 to review (4 cards), 8 to practice (2 questions), the spare 2 -> a card
        assert (len(cards), len(practice)) == (5, 2)
        assert {i["minutes"] for i in cards} == {2} and {i["minutes"] for i in practice} == {3}

    def test_unused_review_minutes_go_to_practice(self):
        items = svc.select_plan_items(
            minutes=25, diagnostic=[], review=[], practice=_many("quiz", 30, "new")
        )
        assert len(items) == 8 and _minutes(items) == 24

    def test_unused_practice_minutes_go_to_review(self):
        items = svc.select_plan_items(
            minutes=25, diagnostic=[], review=_many("card", 30, "review"), practice=[]
        )
        assert len(items) == 12 and _minutes(items) == 24

    def test_never_exceeds_the_minutes_or_the_item_cap(self):
        for minutes in (10, 25, 60, 90):
            items = svc.select_plan_items(
                minutes=minutes,
                diagnostic=_many("quiz", 3, "diagnostic"),
                review=_many("card", 99, "review"),
                practice=_many("quiz", 99, "new"),
            )
            assert _minutes(items) <= minutes
            assert len(items) <= svc.MAX_PLAN_ITEMS

    def test_diagnostic_is_cut_to_the_budget(self):
        items = svc.select_plan_items(
            minutes=10, diagnostic=_many("quiz", 5, "diagnostic"), review=[], practice=[]
        )
        assert len(items) == 3

    def test_deterministic_and_preserves_candidate_order(self):
        kwargs = {
            "minutes": 25,
            "diagnostic": [],
            "review": _many("card", 10, "review"),
            "practice": _many("quiz", 10, "new"),
        }
        first, second = svc.select_plan_items(**kwargs), svc.select_plan_items(**kwargs)
        assert first == second
        ids = [i["item_id"] for i in first if i["item_type"] == "card"]
        assert ids == [f"card{n}" for n in range(len(ids))]


# ── targeted generation request ───────────────────────────────────────


def _gen(status="queued"):
    g = MagicMock()
    g.id = "g-1"
    g.status = status
    return g


@pytest.fixture
def helpers():
    """Patch the query helpers so the flow's order and arguments are what is tested."""
    with (
        patch.object(svc, "_has_processed_artifact", AsyncMock(return_value=True)) as artifact,
        patch.object(svc, "_find_in_flight", AsyncMock(return_value=None)) as in_flight,
        patch.object(svc, "_count_generations_today", AsyncMock(return_value=0)) as today,
        patch.object(svc.quota_service, "check_ai_quota", AsyncMock()) as quota,
    ):
        yield {"artifact": artifact, "in_flight": in_flight, "today": today, "quota": quota}


def _session():
    session = AsyncMock()
    session.add = MagicMock()
    nested = MagicMock()
    nested.__aenter__ = AsyncMock(return_value=None)
    nested.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested = MagicMock(return_value=nested)
    return session


async def _request(session, **over):
    kwargs = {
        "user_id": USER, "user_tier": "free", "course_id": "c-1", "week": 3, "kind": "quiz",
    }  # fmt: skip
    kwargs.update(over)
    return await svc.request_targeted_generation(session, **kwargs)


class TestRequestTargetedGeneration:
    async def test_creates_a_queued_row_for_the_caller(self, helpers):
        session = _session()
        row, created = await _request(session)
        assert created is True
        added = session.add.call_args.args[0]
        assert (added.user_id, added.course_id, added.week, added.kind) == (USER, "c-1", 3, "quiz")
        assert added.status == "queued"
        assert added.requested_count == svc.TARGETED_ITEMS_PER_REQUEST
        assert row is added
        helpers["quota"].assert_awaited_once()
        assert helpers["quota"].await_args.kwargs["calls"] == svc.TARGETED_AI_CALLS

    async def test_every_lookup_is_scoped_to_the_caller(self, helpers):
        await _request(_session())
        assert helpers["artifact"].await_args.kwargs["user_id"] == USER
        assert helpers["in_flight"].await_args.kwargs["user_id"] == USER
        assert helpers["today"].await_args.kwargs["user_id"] == USER
        assert helpers["quota"].await_args.args[1] == USER

    async def test_missing_unit_is_not_found_and_spends_nothing(self, helpers):
        helpers["artifact"].return_value = False
        session = _session()
        with pytest.raises(TargetedUnitNotFoundError):
            await _request(session)
        session.add.assert_not_called()
        helpers["quota"].assert_not_awaited()

    async def test_in_flight_row_is_returned_not_duplicated(self, helpers):
        existing = _gen("running")
        helpers["in_flight"].return_value = existing
        session = _session()
        row, created = await _request(session)
        assert (row, created) == (existing, False)
        session.add.assert_not_called()
        helpers["quota"].assert_not_awaited()
        helpers["today"].assert_not_awaited()

    async def test_daily_cap_refuses_before_the_quota_check(self, helpers):
        helpers["today"].return_value = svc.TARGETED_GENERATIONS_PER_DAY
        with pytest.raises(TargetedDailyCapError) as err:
            await _request(_session())
        assert err.value.limit == svc.TARGETED_GENERATIONS_PER_DAY
        assert err.value.reset_at > datetime.now(UTC)
        assert err.value.reset_at.hour == 0 and err.value.reset_at.tzinfo is not None
        helpers["quota"].assert_not_awaited()

    async def test_one_below_the_cap_is_allowed(self, helpers):
        helpers["today"].return_value = svc.TARGETED_GENERATIONS_PER_DAY - 1
        _, created = await _request(_session())
        assert created is True

    @pytest.mark.parametrize(
        "error",
        [QuotaExceededError("ai_calls", 5, "day"), GlobalCeilingError("ai_calls", 100, 60)],
    )
    async def test_quota_errors_propagate_without_a_row(self, helpers, error):
        helpers["quota"].side_effect = error
        session = _session()
        with pytest.raises(type(error)):
            await _request(session)
        session.add.assert_not_called()

    async def test_unknown_kind_is_rejected(self, helpers):
        with pytest.raises(ValueError):
            await _request(_session(), kind="essay")

    async def test_metric_outcomes(self, helpers):
        def count(outcome):
            return svc.TARGETED_REQUESTS.labels(stage="quiz", outcome=outcome)._value.get()

        before = {o: count(o) for o in ("queued", "existing", "capped", "quota", "not_found")}
        await _request(_session())
        helpers["in_flight"].return_value = _gen()
        await _request(_session())
        helpers["in_flight"].return_value = None
        helpers["today"].return_value = 99
        with pytest.raises(TargetedDailyCapError):
            await _request(_session())
        helpers["today"].return_value = 0
        helpers["quota"].side_effect = QuotaExceededError("ai_calls", 5, "day")
        with pytest.raises(QuotaExceededError):
            await _request(_session())
        helpers["artifact"].return_value = False
        with pytest.raises(TargetedUnitNotFoundError):
            await _request(_session())
        after = {o: count(o) for o in before}
        assert {o: after[o] - before[o] for o in before} == dict.fromkeys(before, 1)


class TestInFlightRace:
    async def test_unique_index_violation_returns_the_winner(self, helpers):
        from sqlalchemy.exc import IntegrityError

        winner = _gen("queued")
        helpers["in_flight"].side_effect = [None, winner]
        session = _session()
        session.flush = AsyncMock(side_effect=IntegrityError("x", {}, Exception()))
        row, created = await _request(session)
        assert (row, created) == (winner, False)


class TestDayBoundaries:
    def test_utc_day_start_is_midnight_utc(self):
        start, reset = svc.utc_day_bounds()
        assert start.hour == start.minute == 0 and start.tzinfo is not None
        assert reset - start == timedelta(days=1)

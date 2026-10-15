"""Weak-spot API (ADR 0007 Decision 7): scoping wiring, consent, cap, enqueue-after-commit."""

from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.exceptions import (
    AiConsentRequiredError,
    QuotaExceededError,
    TargetedDailyCapError,
    TargetedUnitNotFoundError,
)
from app.models.user import User
from app.services import weakspot_service as svc

API = "app.api.weakspots"


def _user() -> MagicMock:
    user = MagicMock(spec=User)
    user.id = "user-1"
    user.tier = "free"
    user.role = "user"
    user.is_active = True
    return user


@pytest.fixture
async def client_user(mock_session):
    from app.api.deps import (
        get_current_user,
        get_current_user_or_default,
        get_user_tz,
        require_ai_consent,
    )
    from app.core.database import get_session
    from app.main import app

    user = _user()

    async def override_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_user_or_default] = lambda: user
    app.dependency_overrides[get_user_tz] = lambda: "Asia/Dubai"
    app.dependency_overrides[require_ai_consent] = lambda: user
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client, user
    app.dependency_overrides.clear()


def _generation(status="queued", **over):
    now = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)
    base = {
        "id": "g-1",
        "course_id": "c-1",
        "week": 3,
        "kind": "quiz",
        "status": status,
        "requested_count": 5,
        "created_count": 0,
        "dropped_duplicate_count": 0,
        "dropped_uncited_count": 0,
        "created_at": now,
        "completed_at": None,
        "error_code": None,
    }
    base.update(over)
    return SimpleNamespace(**base)


def _detail(week=2):
    score = svc.WeekScore("weak", 0.6, 0.5, 0.0, 0.6, 5)
    spot = svc.WeekWeakSpot("c-1", "CSIT302", week, score, "e-1", 4)
    summary = svc.WeekEvidenceSummary(5, 0.4, 2, 1.9, 1, 0)
    return svc.WeakSpotDetail(spot, summary)


class TestHeatmap:
    async def test_groups_by_course_and_scopes_to_the_caller(self, client_user):
        client, user = client_user
        lookup = AsyncMock(return_value=[_detail(2), _detail(5)])
        with patch(f"{API}.weakspot_service.get_weak_spot_details", lookup):
            response = await client.get("/api/weak-spots", params={"course_id": "c-1"})
        assert response.status_code == 200
        assert lookup.await_args.kwargs["user_id"] == user.id
        assert lookup.await_args.kwargs["tz"] == "Asia/Dubai"
        assert lookup.await_args.kwargs["course_id"] == "c-1"
        body = response.json()
        assert len(body["local_date"]) == 10
        course = body["courses"][0]
        assert course["course_id"] == "c-1" and course["course_code"] == "CSIT302"
        assert [w["week"] for w in course["weeks"]] == [2, 5]
        week = course["weeks"][0]
        assert week["status"] == "weak" and week["weakness"] == 0.6
        assert week["evidence"] == {
            "quiz_attempts": 5,
            "quiz_accuracy": 0.4,
            "cards_reviewed": 2,
            "avg_ease": 1.9,
            "lapsed_cards": 1,
            "overdue_cards": 0,
        }
        assert week["next_exam"] == {"exam_id": "e-1", "days_to_exam": 4}

    async def test_unknown_unit_has_null_weakness_and_no_exam(self, client_user):
        client, _ = client_user
        score = svc.WeekScore("unknown", None, 0.0, 0.0, 0.0, 0)
        spot = svc.WeekWeakSpot("c-1", "CSIT302", 1, score, None, None)
        summary = svc.WeekEvidenceSummary(0, None, 0, None, 0, 0)
        detail = svc.WeakSpotDetail(spot, summary)
        with patch(
            f"{API}.weakspot_service.get_weak_spot_details", AsyncMock(return_value=[detail])
        ):
            body = (await client.get("/api/weak-spots")).json()
        week = body["courses"][0]["weeks"][0]
        assert week["weakness"] is None and week["next_exam"] is None
        assert week["evidence"]["quiz_accuracy"] is None


class TestDiagnostic:
    async def test_foreign_course_is_404_with_scoped_lookup(self, client_user):
        client, user = client_user
        lookup = AsyncMock(return_value=None)
        questions = AsyncMock()
        with (
            patch(f"{API}.course_service.get_course_by_id", lookup),
            patch(f"{API}.weakspot_service.get_diagnostic_questions", questions),
        ):
            response = await client.get(
                "/api/weak-spots/diagnostic", params={"course_id": "other", "week": 1}
            )
        assert response.status_code == 404
        assert lookup.await_args.args[1] == "other"
        assert lookup.await_args.kwargs["user_id"] == user.id  # load-bearing
        questions.assert_not_awaited()

    @pytest.mark.parametrize(("count", "needs"), [(0, True), (2, True), (3, False), (5, False)])
    async def test_needs_generation_below_three(self, client_user, count, needs):
        client, user = client_user
        qs = [SimpleNamespace(id=f"q{i}") for i in range(count)]
        questions = AsyncMock(return_value=qs)
        with (
            patch(
                f"{API}.course_service.get_course_by_id",
                AsyncMock(return_value=SimpleNamespace(code="CSIT302")),
            ),
            patch(f"{API}.weakspot_service.get_diagnostic_questions", questions),
        ):
            response = await client.get(
                "/api/weak-spots/diagnostic", params={"course_id": "c-1", "week": 4}
            )
        assert response.status_code == 200
        assert response.json() == {
            "course_id": "c-1",
            "week": 4,
            "question_ids": [q.id for q in qs],
            "items": [{"id": q.id, "course_code": "CSIT302", "week": 4} for q in qs],
            "needs_generation": needs,
        }
        assert questions.await_args.kwargs["user_id"] == user.id


class TestTargeted:
    BODY = {"course_id": "c-1", "week": 3, "kind": "quiz"}

    @pytest.fixture
    def wiring(self):
        with (
            patch(
                f"{API}.weakspot_service.request_targeted_generation",
                AsyncMock(return_value=(_generation(), True)),
            ) as request,
            patch(f"{API}._enqueue_targeted", MagicMock()) as enqueue,
            patch(f"{API}.usage_service.record", AsyncMock(return_value=True)) as record,
        ):
            yield SimpleNamespace(request=request, enqueue=enqueue, record=record)

    async def test_new_request_is_202_and_enqueued_after_commit(
        self, client_user, wiring, mock_session
    ):
        client, user = client_user
        order: list[str] = []
        mock_session.commit.side_effect = lambda: order.append("commit")
        wiring.enqueue.side_effect = lambda gid: order.append(f"enqueue:{gid}")
        response = await client.post("/api/weak-spots/targeted", json=self.BODY)
        assert response.status_code == 202
        assert order == ["commit", "enqueue:g-1"]
        kwargs = wiring.request.await_args.kwargs
        assert kwargs["user_id"] == user.id and kwargs["user_tier"] == "free"
        assert (kwargs["course_id"], kwargs["week"], kwargs["kind"]) == ("c-1", 3, "quiz")
        body = response.json()
        assert body["id"] == "g-1" and body["status"] == "queued" and body["item_ids"] == []
        assert body["error_code"] is None and "error" not in body
        event = wiring.record.await_args
        assert event.args[1] == user.id and event.args[2] == "targeted_generation_requested"
        assert event.kwargs["properties"] == {"count": 5, "week": 3}

    async def test_in_flight_row_is_200_and_not_enqueued(self, client_user, wiring):
        client, _ = client_user
        wiring.request.return_value = (_generation("running"), False)
        response = await client.post("/api/weak-spots/targeted", json=self.BODY)
        assert response.status_code == 200
        assert response.json()["status"] == "running"
        wiring.enqueue.assert_not_called()
        wiring.record.assert_not_awaited()

    async def test_unknown_unit_is_404(self, client_user, wiring):
        client, _ = client_user
        wiring.request.side_effect = TargetedUnitNotFoundError()
        response = await client.post("/api/weak-spots/targeted", json=self.BODY)
        assert response.status_code == 404
        wiring.enqueue.assert_not_called()

    async def test_daily_cap_is_429_with_code_and_reset(self, client_user, wiring):
        client, _ = client_user
        reset = datetime(2026, 10, 16, tzinfo=UTC)
        wiring.request.side_effect = TargetedDailyCapError(limit=6, reset_at=reset)
        response = await client.post("/api/weak-spots/targeted", json=self.BODY)
        assert response.status_code == 429
        body = response.json()
        assert body["code"] == "targeted_daily_cap" and body["limit"] == 6
        assert body["reset_at"].startswith("2026-10-16T00:00:00")
        assert "Retry-After" in response.headers
        wiring.enqueue.assert_not_called()

    async def test_quota_error_uses_the_existing_handler(self, client_user, wiring):
        client, _ = client_user
        wiring.request.side_effect = QuotaExceededError("ai_calls", 5, "day")
        response = await client.post("/api/weak-spots/targeted", json=self.BODY)
        assert response.status_code == 402
        wiring.enqueue.assert_not_called()

    @pytest.mark.parametrize(
        "body",
        [
            {"course_id": "c-1", "week": 3, "kind": "essay"},
            {"course_id": "c-1", "week": 0, "kind": "quiz"},
            {"week": 1},
        ],
    )
    async def test_invalid_body_is_422(self, client_user, wiring, body):
        client, _ = client_user
        assert (await client.post("/api/weak-spots/targeted", json=body)).status_code == 422
        wiring.request.assert_not_awaited()

    async def test_enqueue_failure_frees_the_slot_and_is_503(
        self, client_user, wiring, mock_session
    ):
        client, _ = client_user
        row = _generation()
        wiring.request.return_value = (row, True)
        wiring.enqueue.side_effect = RuntimeError("broker down")
        response = await client.post("/api/weak-spots/targeted", json=self.BODY)
        assert response.status_code == 503
        assert row.status == "failed" and row.error_code == "enqueue_failed"
        assert mock_session.commit.await_count == 2

    async def test_consent_missing_is_403_before_anything_else(self, mock_session):
        from app.api.deps import get_current_user_or_default, require_ai_consent
        from app.core.database import get_session
        from app.main import app

        user = _user()

        async def override_session():
            yield mock_session

        def refuse():
            raise AiConsentRequiredError()

        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[get_current_user_or_default] = lambda: user
        app.dependency_overrides[require_ai_consent] = refuse
        request = AsyncMock()
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                with patch(f"{API}.weakspot_service.request_targeted_generation", request):
                    response = await client.post("/api/weak-spots/targeted", json=self.BODY)
        finally:
            app.dependency_overrides.clear()
        assert response.status_code == 403 and response.json()["code"] == "ai_consent_required"
        request.assert_not_awaited()


class TestTargetedStatus:
    async def test_completed_generation_lists_item_ids(self, client_user):
        client, user = client_user
        row = _generation(
            "completed", created_count=2, completed_at=datetime(2026, 10, 15, tzinfo=UTC)
        )
        lookup = AsyncMock(return_value=row)
        items = AsyncMock(return_value=["q1", "q2"])
        with (
            patch(f"{API}.weakspot_service.get_targeted_generation", lookup),
            patch(f"{API}.weakspot_service.get_generated_item_ids", items),
        ):
            response = await client.get("/api/weak-spots/targeted/g-1")
        assert response.status_code == 200
        assert response.json()["item_ids"] == ["q1", "q2"]
        assert lookup.await_args.args[1] == "g-1"
        assert lookup.await_args.kwargs["user_id"] == user.id
        assert items.await_args.kwargs["user_id"] == user.id

    async def test_running_generation_has_no_items_and_no_item_query(self, client_user):
        client, _ = client_user
        items = AsyncMock()
        with (
            patch(
                f"{API}.weakspot_service.get_targeted_generation",
                AsyncMock(return_value=_generation("running")),
            ),
            patch(f"{API}.weakspot_service.get_generated_item_ids", items),
        ):
            response = await client.get("/api/weak-spots/targeted/g-1")
        assert response.json()["item_ids"] == []
        items.assert_not_awaited()

    async def test_foreign_generation_is_404_and_lookup_scoped(self, client_user):
        client, user = client_user
        lookup = AsyncMock(return_value=None)
        with patch(f"{API}.weakspot_service.get_targeted_generation", lookup):
            response = await client.get("/api/weak-spots/targeted/someone-elses")
        assert response.status_code == 404
        assert lookup.await_args.kwargs.get("user_id") == user.id  # load-bearing


FOCUS = [
    {
        "role": "focus",
        "course_id": "c-1",
        "course_code": "CSIT302",
        "week": 2,
        "status": "weak",
        "weakness": 0.6,
        "priority": 0.7,
        "days_to_exam": 3,
    },
    {
        "role": "diagnostic",
        "course_id": "c-1",
        "course_code": "CSIT302",
        "week": 6,
        "status": "unknown",
        "weakness": None,
        "priority": 0.0,
        "days_to_exam": None,
    },
]

RESOLVED = [
    {
        "item_type": "quiz",
        "item_id": "q1",
        "course_id": "c-1",
        "course_code": "CSIT302",
        "week": 6,
        "reason": "diagnostic",
        "minutes": 3,
        "done": True,
    },
    {
        "item_type": "card",
        "item_id": "f1",
        "course_id": "c-1",
        "course_code": "CSIT302",
        "week": 2,
        "reason": "review",
        "minutes": 2,
        "done": False,
    },
]


def _plan(**over):
    base = {
        "plan_date": date(2026, 10, 15),
        "minutes": 25,
        "version": 1,
        "algorithm_version": 1,
        "built_at": datetime(2026, 10, 15, 4, 0, tzinfo=UTC),
        "items": [],
        "focus": FOCUS,
    }
    base.update(over)
    return SimpleNamespace(**base)


class TestStudyPlan:
    @pytest.fixture
    def plan_wiring(self):
        with (
            patch(
                f"{API}.weakspot_service.get_or_build_tonight_plan",
                AsyncMock(return_value=(_plan(), True)),
            ) as get,
            patch(f"{API}.usage_service.record", AsyncMock(return_value=True)) as record,
            patch(
                f"{API}.weakspot_service.refresh_tonight_plan",
                AsyncMock(return_value=_plan(version=2)),
            ) as refresh,
            patch(
                f"{API}.weakspot_service.resolve_plan_items", AsyncMock(return_value=RESOLVED)
            ) as resolve,
        ):
            yield SimpleNamespace(get=get, refresh=refresh, resolve=resolve, record=record)

    async def test_get_returns_the_plan_with_done_flags(
        self, client_user, plan_wiring, mock_session
    ):
        client, user = client_user
        response = await client.get("/api/study-plan/tonight", params={"minutes": 40})
        assert response.status_code == 200
        kwargs = plan_wiring.get.await_args.kwargs
        assert kwargs["user_id"] == user.id and kwargs["tz"] == "Asia/Dubai"
        assert kwargs["minutes"] == 40
        assert plan_wiring.resolve.await_args.kwargs["user_id"] == user.id
        body = response.json()
        assert body["plan_date"] == "2026-10-15" and body["version"] == 1
        assert body["total_minutes"] == 5 and body["done_count"] == 1
        assert body["items"] == RESOLVED
        assert body["focus"] == [
            {
                "course_id": "c-1",
                "course_code": "CSIT302",
                "week": 2,
                "status": "weak",
                "weakness": 0.6,
                "priority": 0.7,
                "days_to_exam": 3,
            }
        ]
        assert body["diagnostic"] == {"course_id": "c-1", "course_code": "CSIT302", "week": 6}
        mock_session.commit.assert_awaited()

    @pytest.mark.parametrize("minutes", [9, 91])
    async def test_minutes_out_of_range_is_422(self, client_user, plan_wiring, minutes):
        client, _ = client_user
        response = await client.get("/api/study-plan/tonight", params={"minutes": minutes})
        assert response.status_code == 422

    async def test_default_minutes_is_the_adr_default(self, client_user, plan_wiring):
        client, _ = client_user
        await client.get("/api/study-plan/tonight")
        assert plan_wiring.get.await_args.kwargs["minutes"] == svc.DEFAULT_PLAN_MINUTES

    async def test_refresh_rebuilds_for_the_caller(self, client_user, plan_wiring):
        client, user = client_user
        response = await client.post("/api/study-plan/tonight/refresh", json={"minutes": 30})
        assert response.status_code == 200 and response.json()["version"] == 2
        kwargs = plan_wiring.refresh.await_args.kwargs
        assert kwargs["user_id"] == user.id and kwargs["minutes"] == 30
        assert kwargs["tz"] == "Asia/Dubai"

    async def test_built_plan_records_the_event_for_the_caller_reused_does_not(
        self, client_user, plan_wiring
    ):
        client, user = client_user
        await client.get("/api/study-plan/tonight")
        event = plan_wiring.record.await_args
        assert event.args[1] == user.id and event.args[2] == "study_plan_built"
        assert event.kwargs["properties"] == {"count": 0, "duration_seconds": 1500}
        plan_wiring.record.reset_mock()
        plan_wiring.get.return_value = (_plan(), False)
        await client.get("/api/study-plan/tonight")
        plan_wiring.record.assert_not_awaited()
        await client.post("/api/study-plan/tonight/refresh")
        plan_wiring.record.assert_awaited_once()

    async def test_refresh_without_a_body_keeps_the_minutes(self, client_user, plan_wiring):
        client, _ = client_user
        response = await client.post("/api/study-plan/tonight/refresh")
        assert response.status_code == 200
        assert plan_wiring.refresh.await_args.kwargs["minutes"] is None

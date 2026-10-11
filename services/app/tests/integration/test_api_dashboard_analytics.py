"""Dashboard and analytics aggregates over real rows.

The dashboard assembles seven sections and wraps most of them in best-effort
try/except, so a broken query shows up as a missing section rather than an
error. These tests therefore assert that every section is actually present.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.cache import cache_delete, dashboard_cache_key
from app.core.clock import utc_today
from app.core.utils import generate_id
from app.models.deadline import Deadline
from app.models.pipeline_run import PipelineRun

from ._support import seed_course

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _populated_user(client_factory, make_user, db_session, code="DASH101"):
    user = await make_user()
    seeded = await seed_course(db_session, user.id, code=code, flashcards=3, quizzes=2)
    client = client_factory(user)
    exam = await client.post(
        "/api/exams",
        json={
            "course_code": code,
            "title": "Midterm",
            "exam_date": (datetime.now(UTC) + timedelta(days=10)).isoformat(),
            "weeks_scope": [3],
            "target_mastery_pct": 80,
        },
    )
    assert exam.status_code == 201, exam.text
    review = await client.post(
        "/api/study/review", json={"flashcard_id": seeded.flashcards[0].id, "quality": 5}
    )
    assert review.status_code == 200
    q = seeded.questions[0].id
    for correct in (True, False, True):
        await client.post(
            "/api/study/quiz-attempt",
            json={
                "quiz_question_id": q,
                "selected_answer": "A",
                "is_correct": correct,
                "exam_id": exam.json()["id"],
            },
        )
    await client.post(
        f"/api/exams/{exam.json()['id']}/sessions",
        json={
            "cards_reviewed": 5,
            "quiz_questions_answered": 3,
            "quiz_correct": 2,
            "duration_seconds": 900,
        },
    )
    db_session.add(
        Deadline(
            id=generate_id(),
            course_id=seeded.course.id,
            title="Lab 1",
            due_date=utc_today() + timedelta(days=4),
            deadline_type="assignment",
            is_confirmed=True,
        )
    )
    db_session.add(
        PipelineRun(
            id=generate_id(), artifact_id=seeded.artifact.id, stage="assets", status="completed"
        )
    )
    await db_session.flush()
    await cache_delete(dashboard_cache_key(user.id))
    return user, seeded, exam.json()["id"], client


class TestDashboard:
    async def test_every_section_is_populated_for_an_active_user(
        self, client_factory, make_user, db_session
    ):
        user, seeded, exam_id, client = await _populated_user(client_factory, make_user, db_session)
        resp = await client.get("/api/dashboard")
        assert resp.status_code == 200, resp.text
        body = resp.json()

        assert [c["code"] for c in body["courses"]] == ["DASH101"]
        assert body["study_stats"] is not None, "study stats section silently failed"
        assert body["study_stats"]["total"] == 3 and body["study_stats"]["learning"] == 1
        assert [c["course_code"] for c in body["study_stats"]["per_course"]] == ["DASH101"]
        assert [e["exam_id"] for e in body["active_exams"]] == [exam_id]
        assert body["active_exams"][0]["course_code"] == "DASH101"
        assert body["streak"] is not None and body["streak"]["current_streak"] == 1
        assert [d["title"] for d in body["upcoming_deadlines"]] == ["Lab 1"]
        assert body["gamification"] is not None and body["gamification"]["total_xp"] > 0
        assert body["recent_activity"], "pipeline activity missing"
        assert body["pending_review_count"] == 0

    async def test_dashboard_is_cached_then_invalidated(
        self, client_factory, make_user, db_session
    ):
        user, seeded, _, client = await _populated_user(client_factory, make_user, db_session)
        first = (await client.get("/api/dashboard")).json()
        seeded.course.name = "Renamed behind the cache"
        await db_session.flush()
        cached = (await client.get("/api/dashboard")).json()
        assert cached == first  # served from Redis
        await cache_delete(dashboard_cache_key(user.id))
        assert (await client.get("/api/dashboard")).json()["courses"][0][
            "name"
        ] == "Renamed behind the cache"

    async def test_dashboard_never_mixes_tenants(
        self, client_factory, make_user, db_session, two_tenants
    ):
        alice, bob, a, b = two_tenants
        await cache_delete(dashboard_cache_key(alice.id))
        await cache_delete(dashboard_cache_key(bob.id))
        mine = (await client_factory(alice).get("/api/dashboard")).json()
        theirs = (await client_factory(bob).get("/api/dashboard")).json()
        assert [c["id"] for c in mine["courses"]] == [a.course.id]
        assert [c["id"] for c in theirs["courses"]] == [b.course.id]
        assert mine["study_stats"]["total"] == 2 and theirs["study_stats"]["total"] == 1

    async def test_empty_account_dashboard(self, client_factory, make_user):
        user = await make_user()
        await cache_delete(dashboard_cache_key(user.id))
        body = (await client_factory(user).get("/api/dashboard")).json()
        assert (
            body["courses"] == []
            and body["active_exams"] == []
            and body["pending_review_count"] == 0
        )


class TestAnalytics:
    async def test_overview_heatmap_retention_mastery(self, client_factory, make_user, db_session):
        user, seeded, exam_id, client = await _populated_user(client_factory, make_user, db_session)

        overview = (await client.get("/api/analytics/overview")).json()
        assert overview["total_sessions"] >= 1
        assert overview["total_study_hours"] > 0

        heat = (await client.get("/api/analytics/heatmap", params={"days": 30})).json()["days"]
        assert any(d["cards"] == 5 and d["minutes"] == 15 for d in heat)
        assert (await client.get("/api/analytics/heatmap", params={"days": 1})).status_code == 422

        retention = await client.get("/api/analytics/retention", params={"course_code": "DASH101"})
        assert retention.status_code == 200 and retention.json()["points"]
        assert (await client.get("/api/analytics/retention")).status_code == 200

        mastery = (
            await client.get("/api/analytics/mastery", params={"course_code": "DASH101"})
        ).json()
        assert [w["week"] for w in mastery["weeks"]] == [3]
        assert (await client.get("/api/analytics/mastery")).status_code == 200

    async def test_exam_readiness_components(self, client_factory, make_user, db_session):
        user, seeded, exam_id, client = await _populated_user(client_factory, make_user, db_session)
        data = (await client.get(f"/api/analytics/readiness/{exam_id}")).json()
        assert data["exam_id"] == exam_id and data["title"] == "Midterm"
        assert 0 <= data["readiness_score"] <= 100
        assert data["quiz_total"] == 3 and data["quiz_correct"] == 2
        assert data["flashcard_total"] == 3
        assert (await client.get("/api/analytics/readiness/nope")).status_code == 404

    async def test_analytics_are_owner_scoped(
        self, client_factory, make_user, db_session, two_tenants
    ):
        alice, bob, a, b = two_tenants
        _, _, exam_id, _ = await _populated_user(client_factory, make_user, db_session, code="ZZ9")
        stranger = client_factory(bob)
        assert (await stranger.get(f"/api/analytics/readiness/{exam_id}")).status_code == 404
        assert (await stranger.get("/api/analytics/overview")).json()["total_sessions"] == 0
        heat = (await stranger.get("/api/analytics/heatmap")).json()["days"]
        assert all(d["cards"] == 0 for d in heat)
        mastery = (
            await stranger.get("/api/analytics/mastery", params={"course_code": "ZZ9"})
        ).json()
        assert mastery["weeks"] == []

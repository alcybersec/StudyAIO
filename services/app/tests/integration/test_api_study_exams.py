"""Flashcard review (SM-2), quizzes, exams, schedules, streaks and study plans.

Run through the real cookie chain on a seeded course, with a second user that
owns an identically-coded course, so every by-id route is also an IDOR probe.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.exam import Exam
from app.models.flashcard_review import FlashcardReview
from app.models.quiz_attempt import QuizAttempt
from app.models.study_session import StudySession

from ._support import seed_course

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _exam_body(code="NET101", weeks=(3,), days=14, **extra):
    return {
        "course_code": code,
        "title": "Midterm",
        "exam_date": (datetime.now(UTC) + timedelta(days=days)).isoformat(),
        "weeks_scope": list(weeks),
        "target_mastery_pct": 80,
        **extra,
    }


class TestFlashcardReview:
    async def test_due_review_and_scheduling(self, client_factory, make_user, db_session):
        user = await make_user()
        seeded = await seed_course(db_session, user.id, flashcards=3)
        client = client_factory(user)

        due = (await client.get("/api/study/due", params={"course_code": "NET101"})).json()
        assert len(due) == 3
        limited = (await client.get("/api/study/due", params={"limit": 1})).json()
        assert len(limited) == 1
        weekly = (await client.get("/api/study/due", params={"week": 9})).json()
        assert weekly == []

        card = seeded.flashcards[0]
        first = await client.post("/api/study/review", json={"flashcard_id": card.id, "quality": 5})
        assert first.status_code == 200, first.text
        assert first.json()["interval_days"] == 1 and first.json()["repetition_count"] == 1
        second = await client.post(
            "/api/study/review", json={"flashcard_id": card.id, "quality": 5}
        )
        assert second.json()["interval_days"] == 6 and second.json()["repetition_count"] == 2
        lapse = await client.post("/api/study/review", json={"flashcard_id": card.id, "quality": 1})
        assert lapse.json()["repetition_count"] == 0 and lapse.json()["interval_days"] == 1

        reviews = (
            (
                await db_session.execute(
                    select(FlashcardReview).where(FlashcardReview.flashcard_id == card.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(reviews) == 1  # one schedule row per card, updated in place
        assert reviews[0].user_id == user.id

        # Reviewed in the future => no longer due.
        still_due = (await client.get("/api/study/due", params={"course_code": "NET101"})).json()
        assert card.id not in {c["id"] for c in still_due}

        stats = (await client.get("/api/study/stats", params={"course_code": "NET101"})).json()
        assert stats["total"] == 3 and stats["learning"] == 1 and stats["new"] == 2

    async def test_review_validation(self, client_factory, make_user):
        client = client_factory(await make_user())
        assert (
            await client.post("/api/study/review", json={"flashcard_id": "x", "quality": 9})
        ).status_code == 422
        assert (
            await client.post("/api/study/review", json={"flashcard_id": "nope", "quality": 3})
        ).status_code == 404

    async def test_due_and_stats_are_owner_scoped(self, client_factory, two_tenants):
        alice, bob, a, b = two_tenants
        due = (await client_factory(alice).get("/api/study/due")).json()
        assert {c["id"] for c in due} == {c.id for c in a.flashcards}
        stats = (await client_factory(bob).get("/api/study/stats")).json()
        assert stats["total"] == 1

    async def test_cannot_review_another_users_flashcard(
        self, client_factory, two_tenants, db_session
    ):
        alice, bob, a, b = two_tenants
        card = a.flashcards[0]
        await client_factory(alice).post(
            "/api/study/review", json={"flashcard_id": card.id, "quality": 5}
        )
        before = (
            await db_session.execute(
                select(FlashcardReview).where(FlashcardReview.flashcard_id == card.id)
            )
        ).scalar_one()
        interval_before = before.interval_days

        resp = await client_factory(bob).post(
            "/api/study/review", json={"flashcard_id": card.id, "quality": 0}
        )
        assert resp.status_code == 404
        await db_session.refresh(before)
        assert before.interval_days == interval_before


class TestQuizAttempts:
    async def test_attempt_is_recorded(self, client_factory, make_user, db_session):
        user = await make_user()
        seeded = await seed_course(db_session, user.id)
        question = seeded.questions[0]
        resp = await client_factory(user).post(
            "/api/study/quiz-attempt",
            json={
                "quiz_question_id": question.id,
                "selected_answer": "A",
                "is_correct": True,
                "time_spent_ms": 1500,
            },
        )
        assert resp.status_code == 201, resp.text
        stored = (
            await db_session.execute(select(QuizAttempt).where(QuizAttempt.id == resp.json()["id"]))
        ).scalar_one()
        assert stored.is_correct is True and stored.time_spent_ms == 1500
        missing = await client_factory(user).post(
            "/api/study/quiz-attempt",
            json={"quiz_question_id": "nope", "selected_answer": "A", "is_correct": False},
        )
        assert missing.status_code == 404

    async def test_cannot_attempt_another_users_quiz_question(self, client_factory, two_tenants):
        alice, bob, a, b = two_tenants
        resp = await client_factory(bob).post(
            "/api/study/quiz-attempt",
            json={
                "quiz_question_id": a.questions[0].id,
                "selected_answer": "A",
                "is_correct": False,
            },
        )
        assert resp.status_code == 404


class TestTimedPlanAndWeekPlan:
    async def test_timed_plan_budgets_cards_and_quizzes(
        self, client_factory, make_user, db_session
    ):
        user = await make_user()
        seeded = await seed_course(db_session, user.id, flashcards=4, quizzes=4)
        resp = await client_factory(user).post(
            "/api/study/timed-plan", json={"minutes": 30, "course_code": "NET101"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert set(body["card_ids"]) <= {c.id for c in seeded.flashcards} and body["card_ids"]
        assert set(body["quiz_ids"]) <= {q.id for q in seeded.questions} and body["quiz_ids"]
        assert (
            await client_factory(user).post("/api/study/timed-plan", json={"minutes": 1})
        ).status_code == 422

    async def test_timed_plan_contains_only_callers_ids(self, client_factory, two_tenants):
        alice, bob, a, b = two_tenants
        body = (
            await client_factory(bob).post(
                "/api/study/timed-plan", json={"minutes": 60, "course_code": "NET101"}
            )
        ).json()
        mine = {c.id for c in b.flashcards} | {q.id for q in b.questions}
        theirs = {c.id for c in a.flashcards} | {q.id for q in a.questions}
        assert set(body["card_ids"] + body["quiz_ids"]).isdisjoint(theirs)
        assert set(body["card_ids"] + body["quiz_ids"]) <= mine

    async def test_week_plan_and_streak_for_new_user(self, client_factory, make_user):
        client = client_factory(await make_user())
        plan = (await client.get("/api/study/plan")).json()
        assert len(plan["days"]) == 7
        streak = (await client.get("/api/study/streak")).json()
        assert streak == {"current_streak": 0, "longest_streak": 0, "last_study_date": None}


class TestExams:
    async def test_exam_crud_progress_and_derived_views(
        self, client_factory, make_user, db_session
    ):
        user = await make_user()
        seeded = await seed_course(db_session, user.id)
        client = client_factory(user)

        created = await client.post("/api/exams", json=_exam_body())
        assert created.status_code == 201, created.text
        eid = created.json()["id"]
        assert (
            created.json()["course_id"] == seeded.course.id and created.json()["status"] == "active"
        )

        listed = (await client.get("/api/exams")).json()
        assert [e["id"] for e in listed] == [eid]
        assert (await client.get("/api/exams", params={"status": "archived"})).json() == []
        assert len((await client.get("/api/exams", params={"course_code": "NET101"})).json()) == 1

        detail = (await client.get(f"/api/exams/{eid}")).json()
        assert detail["exam_id"] == eid and detail["days_remaining"] in (13, 14)
        assert detail["target_mastery_pct"] == 80

        schedule = (await client.get(f"/api/exams/{eid}/schedule", params={"days": 5})).json()
        assert len(schedule) == 5 and {"date", "priority", "card_target"} <= set(schedule[0])
        today = (await client.get(f"/api/exams/{eid}/today")).json()
        assert today["days_until_exam"] in (13, 14)
        topics = await client.get(f"/api/exams/{eid}/weak-topics")
        assert topics.status_code == 200
        readiness = (await client.get(f"/api/exams/{eid}/readiness")).json()
        assert readiness["exam_id"] == eid and 0 <= readiness["overall"] <= 100

        updated = await client.put(
            f"/api/exams/{eid}", json={"title": "Midterm v2", "target_mastery_pct": 90}
        )
        assert (
            updated.json()["title"] == "Midterm v2" and updated.json()["target_mastery_pct"] == 90
        )

        assert (await client.delete(f"/api/exams/{eid}")).status_code == 204
        archived = (await client.get("/api/exams", params={"status": "archived"})).json()
        assert [e["id"] for e in archived] == [eid]  # soft delete keeps the row

    async def test_study_sessions_feed_history_and_streak(
        self, client_factory, make_user, db_session
    ):
        user = await make_user()
        await seed_course(db_session, user.id)
        client = client_factory(user)
        eid = (await client.post("/api/exams", json=_exam_body())).json()["id"]

        rec = await client.post(
            f"/api/exams/{eid}/sessions",
            json={
                "cards_reviewed": 10,
                "quiz_questions_answered": 4,
                "quiz_correct": 3,
                "duration_seconds": 600,
            },
        )
        assert rec.status_code == 201, rec.text
        stored = (
            await db_session.execute(select(StudySession).where(StudySession.exam_id == eid))
        ).scalar_one()
        assert stored.user_id == user.id and stored.cards_reviewed == 10

        history = (await client.get(f"/api/exams/{eid}/history")).json()
        assert history[0]["cards_reviewed"] == 10 and history[0]["session_count"] == 1
        streak = (await client.get("/api/study/streak")).json()
        assert streak["current_streak"] == 1 and streak["longest_streak"] == 1
        stats = await client.get("/api/gamification/xp")
        assert stats.status_code == 200

    async def test_exam_validation(self, client_factory, make_user, db_session):
        user = await make_user()
        await seed_course(db_session, user.id)
        client = client_factory(user)
        assert (await client.post("/api/exams", json=_exam_body(code="NOPE"))).status_code == 400
        assert (await client.post("/api/exams", json=_exam_body(weeks=()))).status_code == 422
        assert (
            await client.post("/api/exams", json=_exam_body(target_mastery_pct=0))
        ).status_code == 422

    async def test_exam_routes_are_owner_scoped(self, client_factory, two_tenants):
        alice, bob, a, b = two_tenants
        eid = (await client_factory(alice).post("/api/exams", json=_exam_body())).json()["id"]
        other = client_factory(bob)

        assert (await other.get("/api/exams")).json() == []
        for method, path, kwargs in (
            ("GET", f"/api/exams/{eid}", {}),
            ("PUT", f"/api/exams/{eid}", {"json": {"title": "stolen"}}),
            ("DELETE", f"/api/exams/{eid}", {}),
            ("GET", f"/api/exams/{eid}/schedule", {}),
            ("GET", f"/api/exams/{eid}/today", {}),
            ("GET", f"/api/exams/{eid}/weak-topics", {}),
            ("GET", f"/api/exams/{eid}/readiness", {}),
            (
                "POST",
                f"/api/exams/{eid}/sessions",
                {"json": {"cards_reviewed": 1, "duration_seconds": 60}},
            ),
        ):
            resp = await other.request(method, path, **kwargs)
            assert resp.status_code == 404, (method, path, resp.status_code)
        # Nothing the stranger tried changed the exam.
        still = (await client_factory(alice).get(f"/api/exams/{eid}")).json()
        assert still["title"] == "Midterm" and still["status"] == "active"
        assert (await other.get(f"/api/exams/{eid}/history")).json() == []

    async def test_exam_creation_is_scoped_to_own_course_code(
        self, client_factory, make_user, db_session
    ):
        owner, stranger = await make_user(), await make_user()
        await seed_course(db_session, owner.id, code="ONLYMINE")
        resp = await client_factory(stranger).post("/api/exams", json=_exam_body(code="ONLYMINE"))
        assert resp.status_code == 400
        assert (
            await db_session.execute(select(Exam).where(Exam.user_id == stranger.id))
        ).first() is None

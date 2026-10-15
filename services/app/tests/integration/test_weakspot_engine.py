"""Weak-spot engine (ADR 0007) against a real database: services.weakspot v1, api.weak-spots v1.

What a mocked session cannot show: the scoring SQL (owner joins, the 90-day window,
user-local exam dates), the unique (user_id, plan_date) plan row, the partial unique
index that lets one targeted request per unit be in flight, the batch fetch's
owner/archived filters, and that nothing a targeted request created is lost to a
pipeline re-run (floor 4) or left behind by account deletion.

AI is never reached: the worker task is enqueued by name and that call is mocked, and
the AI quota check is patched where a test is about something else.
"""

import asyncio
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import func, select

from app.core.clock import user_today
from app.core.database import async_session_factory
from app.core.utils import generate_id
from app.models.artifact import LectureArtifact
from app.models.course import Course
from app.models.exam import Exam
from app.models.flashcard import Flashcard
from app.models.flashcard_review import FlashcardReview
from app.models.quiz import QuizQuestion
from app.models.quiz_attempt import QuizAttempt
from app.models.study_plan import StudyPlan
from app.models.targeted_generation import TargetedGeneration
from app.models.user_settings import UserSettings
from app.services import account_service, asset_service, exam_service, usage_service
from app.services import weakspot_service as ws

from ._support import seed_course

pytestmark = pytest.mark.asyncio(loop_scope="session")

ENQUEUE = "app.api.weakspots._enqueue_targeted"
QUOTA = "app.services.weakspot_service.quota_service.check_ai_quota"


# ── builders ───────────────────────────────────────────────────────────


async def _world(db, user, *, code="WSP101", week=1):
    """A course with one processed artifact and no study items."""
    return await seed_course(
        db, user.id, code=code, week=week, flashcards=0, quizzes=0, with_chunks=False
    )


async def _questions(db, world, week, n, *, origin="pipeline", generation_id=None) -> list[str]:
    ids = []
    for i in range(n):
        q = QuizQuestion(
            id=generate_id(),
            course_id=world.course.id,
            week=week,
            question_type="short_answer",
            question=f"w{week} q{i}",
            correct_answer="a",
            explanation="e",
            source_artifact_id=world.artifact.id,
            source_page_ref=1,
            origin=origin,
            targeted_generation_id=generation_id,
            focus_topic="topic" if origin == "targeted" else None,
        )
        db.add(q)
        ids.append(q.id)
    await db.flush()
    return ids


async def _cards(db, world, week, n) -> list[str]:
    ids = []
    for i in range(n):
        c = Flashcard(
            id=generate_id(),
            course_id=world.course.id,
            week=week,
            front=f"w{week} f{i}",
            back="b",
            tags=[],
            source_artifact_id=world.artifact.id,
            source_page_ref=1,
        )
        db.add(c)
        ids.append(c.id)
    await db.flush()
    return ids


async def _attempts(db, qids, correct: list[bool], *, age_days: float = 0.0) -> None:
    at = datetime.now(UTC) - timedelta(days=age_days)
    for qid, ok in zip(qids, correct, strict=True):
        db.add(QuizAttempt(quiz_question_id=qid, selected_answer="x", is_correct=ok, created_at=at))
    await db.flush()


async def _set_tz(db, user, tz: str) -> None:
    db.add(UserSettings(id=generate_id(), user_id=user.id, settings_json={}, timezone=tz))
    await db.flush()


async def _scored_world(db, user):
    """Weeks 1-4 of one course: weak, shaky, solid and unknown."""
    world = await _world(db, user)
    q = {w: await _questions(db, world, w, 5 if w < 4 else 2) for w in (1, 2, 3, 4)}
    await _attempts(db, q[1], [False] * 5)
    await _attempts(db, q[2], [True] * 4 + [False])
    await _attempts(db, q[3], [True] * 5)
    await _attempts(db, q[4], [False] * 2)
    return world, q


def _weeks(body, course_id) -> dict[int, dict]:
    (course,) = [c for c in body["courses"] if c["course_id"] == course_id]
    return {w["week"]: w for w in course["weeks"]}


@contextmanager
def _enqueue_mocked():
    with patch(ENQUEUE) as enqueue, patch(QUOTA, AsyncMock()):
        yield enqueue


# ── scores ─────────────────────────────────────────────────────────────


class TestScores:
    async def test_unknown_weak_shaky_and_solid_at_the_adr_thresholds(
        self, make_user, client_factory, db_session
    ):
        user = await make_user()
        world, _ = await _scored_world(db_session, user)

        resp = await client_factory(user).get("/api/weak-spots")

        assert resp.status_code == 200, resp.text
        weeks = _weeks(resp.json(), world.course.id)
        assert {w: weeks[w]["status"] for w in weeks} == {
            1: "weak",
            2: "shaky",
            3: "solid",
            4: "unknown",
        }
        assert weeks[1]["weakness"] >= ws.WEAK_THRESHOLD
        assert ws.SOLID_THRESHOLD <= weeks[2]["weakness"] < ws.WEAK_THRESHOLD
        assert weeks[3]["weakness"] < ws.SOLID_THRESHOLD
        # Too little evidence to call: no weakness, no priority, and the counts say why.
        assert weeks[4]["weakness"] is None and weeks[4]["priority"] == 0.0
        assert weeks[4]["evidence"]["quiz_attempts"] == 2
        assert weeks[1]["evidence"]["quiz_accuracy"] == 0.0
        assert weeks[3]["evidence"]["quiz_accuracy"] == 1.0

    async def test_ranked_weakest_first(self, make_user, client_factory, db_session):
        user = await make_user()
        world, _ = await _scored_world(db_session, user)

        body = (await client_factory(user).get("/api/weak-spots")).json()

        (course,) = [c for c in body["courses"] if c["course_id"] == world.course.id]
        order = [w["week"] for w in course["weeks"]]
        assert order.index(1) < order.index(2) < order.index(3)

    async def test_attempts_outside_the_window_are_not_evidence(
        self, make_user, client_factory, db_session
    ):
        user = await make_user()
        world = await _world(db_session, user)
        qids = await _questions(db_session, world, 1, 5)
        await _attempts(db_session, qids, [False] * 5, age_days=ws.QUIZ_WINDOW_DAYS + 5)

        weeks = _weeks((await client_factory(user).get("/api/weak-spots")).json(), world.course.id)

        assert weeks[1]["status"] == "unknown"
        assert weeks[1]["evidence"]["quiz_attempts"] == 0

    async def test_card_reviews_count_as_evidence(self, make_user, client_factory, db_session):
        user = await make_user()
        world = await _world(db_session, user)
        cards = await _cards(db_session, world, 2, 3)
        now = datetime.now(UTC)
        for cid in cards:
            db_session.add(
                FlashcardReview(
                    user_id=user.id,
                    flashcard_id=cid,
                    ease_factor=ws.EASE_FLOOR,
                    interval_days=1,
                    repetition_count=0,
                    next_review_at=now - timedelta(days=3),
                    last_reviewed_at=now - timedelta(days=4),
                )
            )
        await db_session.flush()

        weeks = _weeks((await client_factory(user).get("/api/weak-spots")).json(), world.course.id)

        assert weeks[2]["status"] == "weak"
        ev = weeks[2]["evidence"]
        assert (ev["cards_reviewed"], ev["lapsed_cards"], ev["overdue_cards"]) == (3, 3, 3)

    async def test_archived_questions_do_not_create_a_unit(
        self, make_user, client_factory, db_session
    ):
        user = await make_user()
        world = await _world(db_session, user)
        (qid,) = await _questions(db_session, world, 6, 1)
        (await db_session.get(QuizQuestion, qid)).archived_at = datetime.now(UTC)
        await db_session.flush()

        weeks = _weeks((await client_factory(user).get("/api/weak-spots")).json(), world.course.id)

        assert 6 not in weeks

    async def test_exam_urgency_uses_the_users_local_date(
        self, make_user, client_factory, db_session
    ):
        user = await make_user()
        world, _ = await _scored_world(db_session, user)
        # A pinned clock: 10:00Z is the 16th in Kiritimati, the 14th in Pago Pago, the 15th in UTC.
        now = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)
        exam_at = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)
        db_session.add(
            Exam(
                id=generate_id(),
                user_id=user.id,
                course_id=world.course.id,
                title="midterm",
                exam_date=exam_at,
                weeks_scope=[1, 3],
            )
        )
        await db_session.flush()
        east, west = "Pacific/Kiritimati", "Pacific/Pago_Pago"

        results = {}
        for tz in (east, west):
            with patch("app.core.clock.utc_now", return_value=now):
                details = await ws.get_weak_spot_details(db_session, user_id=user.id, tz=tz)
            results[tz] = {d.spot.week: d for d in details if d.spot.course_id == world.course.id}

        assert results[east][1].spot.days_to_exam == 3
        assert results[west][1].spot.days_to_exam == 4
        near, far = results[east][1].spot.score, results[west][1].spot.score
        assert near.urgency > far.urgency > 0
        assert near.priority > far.priority
        # A week outside the exam's scope is untouched by it.
        assert results[east][2].spot.days_to_exam is None
        assert results[east][2].spot.score.urgency == 0.0

    async def test_exam_shows_through_the_api_with_the_stored_zone(
        self, make_user, client_factory, db_session
    ):
        user = await make_user()
        await _set_tz(db_session, user, "Pacific/Kiritimati")
        world, _ = await _scored_world(db_session, user)
        exam_at = datetime.now(UTC) + timedelta(days=5)
        exam = Exam(
            id=generate_id(),
            user_id=user.id,
            course_id=world.course.id,
            title="final",
            exam_date=exam_at,
            weeks_scope=[1],
        )
        db_session.add(exam)
        await db_session.flush()

        body = (await client_factory(user).get("/api/weak-spots")).json()

        week = _weeks(body, world.course.id)[1]
        assert week["next_exam"] == {
            "exam_id": exam.id,
            "days_to_exam": exam_service.days_until(exam_at, "Pacific/Kiritimati"),
        }
        assert body["local_date"] == user_today("Pacific/Kiritimati").isoformat()

    async def test_course_filter_and_unauthenticated(self, make_user, client_factory, db_session):
        user = await make_user()
        first, _ = await _scored_world(db_session, user)
        second = await _world(db_session, user, code="WSP202")
        await _questions(db_session, second, 1, 1)

        body = (
            await client_factory(user).get(
                "/api/weak-spots", params={"course_id": second.course.id}
            )
        ).json()

        assert [c["course_id"] for c in body["courses"]] == [second.course.id]
        assert (await client_factory().get("/api/weak-spots")).status_code == 401


# ── tonight's plan ─────────────────────────────────────────────────────


async def _plan_world(db, user):
    """Weak week 1 (cards + missed questions) and an unknown, diagnosable week 4."""
    world, q = await _scored_world(db, user)
    cards = await _cards(db, world, 1, 3)
    return world, q, cards


class TestTonightPlan:
    async def test_built_once_per_local_day_and_stable(self, make_user, client_factory, db_session):
        user = await make_user()
        # Whichever of these zones is on a different calendar date than UTC proves the zone is used.
        tz = next(
            z
            for z in ("Pacific/Kiritimati", "Pacific/Pago_Pago")
            if user_today(z) != user_today("UTC")
        )
        await _set_tz(db_session, user, tz)
        await _plan_world(db_session, user)
        client = client_factory(user)

        first = (await client.get("/api/study-plan/tonight")).json()
        # New evidence arrives, but the day's plan does not reshuffle under the user.
        second = (await client.get("/api/study-plan/tonight", params={"minutes": 60})).json()

        assert first["plan_date"] == user_today(tz).isoformat() != user_today("UTC").isoformat()
        assert first["items"], "a weak week with cards and missed questions yields a plan"
        assert second["items"] == first["items"]
        assert (second["version"], second["minutes"], second["built_at"]) == (
            1,
            ws.DEFAULT_PLAN_MINUTES,
            first["built_at"],
        )
        rows = await db_session.scalar(
            select(func.count()).select_from(StudyPlan).where(StudyPlan.user_id == user.id)
        )
        assert rows == 1

    async def test_plan_composition_and_budget(self, make_user, client_factory, db_session):
        user = await make_user()
        world, q, cards = await _plan_world(db_session, user)

        plan = (await client_factory(user).get("/api/study-plan/tonight")).json()

        reasons = {i["reason"] for i in plan["items"]}
        assert "missed" in reasons and "review" in reasons
        assert plan["diagnostic"] == {
            "course_id": world.course.id,
            "course_code": world.course.code,
            "week": 4,
        }
        diag = [i for i in plan["items"] if i["reason"] == "diagnostic"]
        assert 0 < len(diag) <= ws.DIAGNOSTIC_QUESTIONS
        assert all(i["item_type"] == "quiz" and i["item_id"] in q[4] for i in diag)
        assert plan["items"][: len(diag)] == diag, "the diagnostic comes first"
        assert {f["week"] for f in plan["focus"]} == {1, 2}
        assert plan["total_minutes"] == sum(i["minutes"] for i in plan["items"])
        assert plan["total_minutes"] <= plan["minutes"]
        assert plan["done_count"] == 0 and not any(i["done"] for i in plan["items"])
        assert len(plan["items"]) <= ws.MAX_PLAN_ITEMS
        assert {i["item_id"] for i in plan["items"] if i["item_type"] == "card"} <= set(cards)

    async def test_refresh_rebuilds_and_bumps_the_version(
        self, make_user, client_factory, db_session
    ):
        user = await make_user()
        world, q, _ = await _plan_world(db_session, user)
        client = client_factory(user)
        first = (await client.get("/api/study-plan/tonight")).json()
        # Week 4 becomes weak: the rebuilt plan must see the new evidence.
        await _attempts(db_session, q[4][:1], [False])
        extra = await _questions(db_session, world, 4, 2)
        await _attempts(db_session, extra, [False, False])

        refreshed = await client.post("/api/study-plan/tonight/refresh", json={"minutes": 40})

        assert refreshed.status_code == 200, refreshed.text
        body = refreshed.json()
        assert (body["version"], body["minutes"]) == (2, 40)
        assert body["diagnostic"] is None
        assert {f["week"] for f in body["focus"]} == {1, 2, 4}
        assert body["items"] != first["items"]
        assert body["built_at"] > first["built_at"]
        # The follow-up read returns the refreshed plan, and there is still one row.
        assert (await client.get("/api/study-plan/tonight")).json()["version"] == 2
        assert (
            await db_session.scalar(
                select(func.count()).select_from(StudyPlan).where(StudyPlan.user_id == user.id)
            )
        ) == 1
        assert (
            await client.post("/api/study-plan/tonight/refresh", json={"minutes": 5})
        ).status_code == 422

    async def test_refresh_without_a_plan_builds_one(self, make_user, client_factory, db_session):
        user = await make_user()
        await _plan_world(db_session, user)

        body = (await client_factory(user).post("/api/study-plan/tonight/refresh")).json()

        assert body["version"] == 1 and body["items"]

    async def test_done_flips_after_a_real_review_and_attempt(
        self, make_user, client_factory, db_session
    ):
        user = await make_user()
        await _plan_world(db_session, user)
        client = client_factory(user)
        plan = (await client.get("/api/study-plan/tonight")).json()
        card = next(i for i in plan["items"] if i["item_type"] == "card")
        quiz = next(i for i in plan["items"] if i["item_type"] == "quiz")

        reviewed = await client.post(
            "/api/study/review", json={"flashcard_id": card["item_id"], "quality": 4}
        )
        answered = await client.post(
            "/api/study/quiz-attempt",
            json={"quiz_question_id": quiz["item_id"], "selected_answer": "a", "is_correct": True},
        )
        assert reviewed.status_code in (200, 201), reviewed.text
        assert answered.status_code == 201, answered.text

        after = (await client.get("/api/study-plan/tonight")).json()

        done = {(i["item_type"], i["item_id"]) for i in after["items"] if i["done"]}
        assert done == {("card", card["item_id"]), ("quiz", quiz["item_id"])}
        assert after["done_count"] == 2
        assert [(i["item_type"], i["item_id"]) for i in after["items"]] == [
            (i["item_type"], i["item_id"]) for i in plan["items"]
        ], "order and membership stay frozen"

    async def test_work_before_the_plan_was_built_is_not_done(
        self, make_user, client_factory, db_session
    ):
        user = await make_user()
        _, q, _ = await _plan_world(db_session, user)
        # q[1] was attempted (wrongly) when the world was seeded, before any plan existed.
        plan = (await client_factory(user).get("/api/study-plan/tonight")).json()

        missed = [i for i in plan["items"] if i["reason"] == "missed"]
        assert missed and all(i["item_id"] in q[1] + q[2] for i in missed)
        assert not any(i["done"] for i in plan["items"])

    async def test_archived_items_are_dropped_from_the_plan(
        self, make_user, client_factory, db_session
    ):
        user = await make_user()
        await _plan_world(db_session, user)
        client = client_factory(user)
        plan = (await client.get("/api/study-plan/tonight")).json()
        victim = plan["items"][0]
        model = Flashcard if victim["item_type"] == "card" else QuizQuestion
        (await db_session.get(model, victim["item_id"])).archived_at = datetime.now(UTC)
        await db_session.flush()

        after = (await client.get("/api/study-plan/tonight")).json()

        assert victim["item_id"] not in {i["item_id"] for i in after["items"]}
        assert len(after["items"]) == len(plan["items"]) - 1

    async def test_minutes_out_of_range_is_422(self, make_user, client_factory):
        client = client_factory(await make_user())
        assert (
            await client.get("/api/study-plan/tonight", params={"minutes": 5})
        ).status_code == 422
        assert (
            await client.get("/api/study-plan/tonight", params={"minutes": 91})
        ).status_code == 422


# ── diagnostic ─────────────────────────────────────────────────────────


class TestDiagnostic:
    async def test_at_most_five_existing_questions_never_attempted_first(
        self, make_user, client_factory, db_session
    ):
        user = await make_user()
        world = await _world(db_session, user)
        qids = await _questions(db_session, world, 5, 8)
        await _attempts(db_session, qids[:4], [True] * 4)

        resp = await client_factory(user).get(
            "/api/weak-spots/diagnostic", params={"course_id": world.course.id, "week": 5}
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body["question_ids"]) == ws.DIAGNOSTIC_QUESTIONS_MAX == 5
        ids = body["question_ids"]
        assert set(ids[:4]) == set(qids[4:]), "never-attempted questions come first"
        assert ids[4] in qids[:4]
        assert body["needs_generation"] is False
        assert body["items"] == [
            {"id": qid, "course_code": world.course.code, "week": 5} for qid in body["question_ids"]
        ]

    async def test_few_questions_need_generation(self, make_user, client_factory, db_session):
        user = await make_user()
        world = await _world(db_session, user)
        await _questions(db_session, world, 2, 2)

        body = (
            await client_factory(user).get(
                "/api/weak-spots/diagnostic", params={"course_id": world.course.id, "week": 2}
            )
        ).json()

        assert len(body["question_ids"]) == 2 and body["needs_generation"] is True

    async def test_archived_questions_are_excluded(self, make_user, client_factory, db_session):
        user = await make_user()
        world = await _world(db_session, user)
        qids = await _questions(db_session, world, 2, 4)
        (await db_session.get(QuizQuestion, qids[0])).archived_at = datetime.now(UTC)
        await db_session.flush()

        body = (
            await client_factory(user).get(
                "/api/weak-spots/diagnostic", params={"course_id": world.course.id, "week": 2}
            )
        ).json()

        assert qids[0] not in body["question_ids"] and len(body["question_ids"]) == 3

    async def test_unknown_course_is_404(self, make_user, client_factory):
        resp = await client_factory(await make_user()).get(
            "/api/weak-spots/diagnostic", params={"course_id": generate_id(), "week": 1}
        )
        assert resp.status_code == 404


# ── targeted request ───────────────────────────────────────────────────


class TestTargetedRequest:
    @staticmethod
    def _body(world, week=1, kind="quiz"):
        return {"course_id": world.course.id, "week": week, "kind": kind}

    async def test_consent_is_required(self, make_user, client_factory, db_session):
        user = await make_user(consented=False)
        world = await _world(db_session, user)

        with _enqueue_mocked() as enqueue:
            resp = await client_factory(user).post(
                "/api/weak-spots/targeted", json=self._body(world)
            )

        assert resp.status_code == 403
        enqueue.assert_not_called()
        assert (
            await db_session.scalar(
                select(func.count())
                .select_from(TargetedGeneration)
                .where(TargetedGeneration.user_id == user.id)
            )
        ) == 0

    async def test_new_request_is_202_and_enqueues_by_id(
        self, make_user, client_factory, db_session
    ):
        user = await make_user()
        world = await _world(db_session, user)

        with _enqueue_mocked() as enqueue:
            resp = await client_factory(user).post(
                "/api/weak-spots/targeted", json=self._body(world)
            )

        assert resp.status_code == 202, resp.text
        body = resp.json()
        assert (body["status"], body["kind"], body["week"], body["item_ids"]) == (
            "queued",
            "quiz",
            1,
            [],
        )
        assert body["requested_count"] == ws.TARGETED_ITEMS_PER_REQUEST
        enqueue.assert_called_once_with(body["id"])
        assert "error_code" in body and "prompt" not in body

    async def test_in_flight_request_returns_the_existing_row(
        self, make_user, client_factory, db_session
    ):
        user = await make_user()
        world = await _world(db_session, user)
        client = client_factory(user)

        with _enqueue_mocked() as enqueue:
            first = await client.post("/api/weak-spots/targeted", json=self._body(world))
            again = await client.post("/api/weak-spots/targeted", json=self._body(world))
            other_kind = await client.post(
                "/api/weak-spots/targeted", json=self._body(world, kind="flashcards")
            )

        assert (first.status_code, again.status_code, other_kind.status_code) == (202, 200, 202)
        assert again.json()["id"] == first.json()["id"]
        assert other_kind.json()["id"] != first.json()["id"]
        assert enqueue.call_count == 2
        assert (
            await db_session.scalar(
                select(func.count())
                .select_from(TargetedGeneration)
                .where(TargetedGeneration.user_id == user.id)
            )
        ) == 2

    async def test_a_finished_job_frees_the_unit(self, make_user, client_factory, db_session):
        user = await make_user()
        world = await _world(db_session, user)
        client = client_factory(user)
        with _enqueue_mocked():
            first = (await client.post("/api/weak-spots/targeted", json=self._body(world))).json()
            (await db_session.get(TargetedGeneration, first["id"])).status = "completed"
            await db_session.flush()
            second = await client.post("/api/weak-spots/targeted", json=self._body(world))

        assert second.status_code == 202 and second.json()["id"] != first["id"]

    async def test_daily_cap_is_429_with_code_reset_and_retry_after(
        self, make_user, client_factory, db_session
    ):
        user = await make_user()
        world = await _world(db_session, user)
        for week in range(1, ws.TARGETED_GENERATIONS_PER_DAY + 1):
            db_session.add(
                TargetedGeneration(
                    user_id=user.id,
                    course_id=world.course.id,
                    week=week,
                    kind="quiz",
                    status="completed",
                    requested_count=5,
                    topics=[],
                )
            )
        await db_session.flush()

        with _enqueue_mocked() as enqueue:
            resp = await client_factory(user).post(
                "/api/weak-spots/targeted", json=self._body(world)
            )

        assert resp.status_code == 429, resp.text
        body = resp.json()
        assert (body["code"], body["limit"]) == ("targeted_daily_cap", 6)
        reset_at = datetime.fromisoformat(body["reset_at"])
        assert reset_at.tzinfo is not None
        assert (reset_at.hour, reset_at.minute, reset_at.second) == (0, 0, 0)
        assert datetime.now(UTC) < reset_at <= datetime.now(UTC) + timedelta(days=1)
        assert 1 <= int(resp.headers["Retry-After"]) <= 86400
        enqueue.assert_not_called()

    async def test_the_cap_counts_per_user(self, make_user, client_factory, db_session):
        capped, other = await make_user(), await make_user()
        world = await _world(db_session, capped)
        theirs = await _world(db_session, other, code="WSP303")
        for week in range(1, 7):
            db_session.add(
                TargetedGeneration(
                    user_id=capped.id,
                    course_id=world.course.id,
                    week=week,
                    kind="quiz",
                    status="completed",
                    requested_count=5,
                    topics=[],
                )
            )
        await db_session.flush()

        with _enqueue_mocked():
            resp = await client_factory(other).post(
                "/api/weak-spots/targeted", json=self._body(theirs)
            )

        assert resp.status_code == 202

    async def test_unit_without_processed_material_is_404(
        self, make_user, client_factory, db_session
    ):
        user = await make_user()
        world = await _world(db_session, user)

        with _enqueue_mocked() as enqueue:
            wrong_week = await client_factory(user).post(
                "/api/weak-spots/targeted", json=self._body(world, week=9)
            )
            no_course = await client_factory(user).post(
                "/api/weak-spots/targeted",
                json={"course_id": generate_id(), "week": 1, "kind": "quiz"},
            )

        assert (wrong_week.status_code, no_course.status_code) == (404, 404)
        enqueue.assert_not_called()

    async def test_invalid_bodies_are_422(self, make_user, client_factory, db_session):
        user = await make_user()
        world = await _world(db_session, user)
        client = client_factory(user)
        for bad in (
            {**self._body(world), "kind": "essay"},
            {**self._body(world), "week": 0},
            {**self._body(world), "extra": 1},
        ):
            assert (await client.post("/api/weak-spots/targeted", json=bad)).status_code == 422

    async def test_enqueue_failure_is_503_and_frees_the_slot(
        self, make_user, client_factory, db_session
    ):
        user = await make_user()
        world = await _world(db_session, user)
        client = client_factory(user)

        with patch(ENQUEUE, side_effect=RuntimeError("broker down")), patch(QUOTA, AsyncMock()):
            failed = await client.post("/api/weak-spots/targeted", json=self._body(world))
        with _enqueue_mocked():
            retry = await client.post("/api/weak-spots/targeted", json=self._body(world))

        assert failed.status_code == 503
        assert retry.status_code == 202
        row = (
            await db_session.execute(
                select(TargetedGeneration).where(
                    TargetedGeneration.user_id == user.id, TargetedGeneration.status == "failed"
                )
            )
        ).scalar_one()
        assert row.error_code == "enqueue_failed"

    async def test_polling_returns_created_items_only_when_completed(
        self, make_user, client_factory, db_session
    ):
        user = await make_user()
        world = await _world(db_session, user)
        client = client_factory(user)
        with _enqueue_mocked():
            gen = (await client.post("/api/weak-spots/targeted", json=self._body(world))).json()
        queued = (await client.get(f"/api/weak-spots/targeted/{gen['id']}")).json()
        ids = await _questions(db_session, world, 1, 2, origin="targeted", generation_id=gen["id"])
        row = await db_session.get(TargetedGeneration, gen["id"])
        row.status, row.created_count = "completed", 2
        await db_session.flush()

        done = (await client.get(f"/api/weak-spots/targeted/{gen['id']}")).json()

        assert queued["item_ids"] == []
        assert sorted(done["item_ids"]) == sorted(ids) and done["created_count"] == 2


class TestTargetedRace:
    async def test_two_sessions_racing_on_one_unit_get_one_row(self, committed_user):
        user = await committed_user()
        async with async_session_factory() as s:
            course = Course(id=generate_id(), code="RACE1", name="race", user_id=user.id)
            s.add(course)
            await s.flush()
            s.add(
                LectureArtifact(
                    id=generate_id(),
                    user_id=user.id,
                    course_id=course.id,
                    week=1,
                    original_filename="r.pdf",
                    file_path=f"uploads/{generate_id()}",
                    file_type="pdf",
                    sha256=generate_id().replace("-", "") * 2,
                    file_size_bytes=1,
                    status="processed",
                )
            )
            await s.commit()
        # Both sessions pass the in-flight check before either inserts, so the partial
        # unique index (not the application check) is what decides the winner.
        barrier = asyncio.Barrier(2)

        async def quota(*_a, **_k):
            await barrier.wait()

        async def click():
            async with async_session_factory() as s:
                row, created = await ws.request_targeted_generation(
                    s, user_id=user.id, user_tier="free", course_id=course.id, week=1, kind="quiz"
                )
                await s.commit()
                return row.id, created

        with patch(QUOTA, quota):
            results = await asyncio.wait_for(asyncio.gather(click(), click()), timeout=30)

        assert len({rid for rid, _ in results}) == 1
        assert sorted(created for _, created in results) == [False, True]
        async with async_session_factory() as s:
            rows = await s.scalar(
                select(func.count())
                .select_from(TargetedGeneration)
                .where(TargetedGeneration.user_id == user.id)
            )
        assert rows == 1


# ── batch fetch ────────────────────────────────────────────────────────


class TestStudyItems:
    async def test_only_the_callers_active_items_come_back(
        self, make_user, client_factory, db_session
    ):
        alice, bob = await make_user(), await make_user()
        a, b = await _world(db_session, alice), await _world(db_session, bob, code="WSP909")
        a_cards, a_qs = await _cards(db_session, a, 1, 2), await _questions(db_session, a, 1, 3)
        b_cards, b_qs = await _cards(db_session, b, 1, 1), await _questions(db_session, b, 1, 1)
        (await db_session.get(Flashcard, a_cards[1])).archived_at = datetime.now(UTC)
        (await db_session.get(QuizQuestion, a_qs[2])).archived_at = datetime.now(UTC)
        await db_session.flush()

        resp = await client_factory(alice).get(
            "/api/study/items",
            params={
                "flashcard_ids": [a_cards[0], a_cards[1], *b_cards, generate_id()],
                "quiz_question_ids": [*a_qs, *b_qs, generate_id()],
            },
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert [c["id"] for c in body["flashcards"]] == [a_cards[0]]
        assert sorted(q["id"] for q in body["quiz_questions"]) == sorted(a_qs[:2])
        assert body["flashcards"][0]["origin"] == "pipeline"

    async def test_targeted_items_carry_their_provenance(
        self, make_user, client_factory, db_session
    ):
        user = await make_user()
        world = await _world(db_session, user)
        gen = TargetedGeneration(
            user_id=user.id,
            course_id=world.course.id,
            week=1,
            kind="quiz",
            status="completed",
            requested_count=5,
            topics=[],
        )
        db_session.add(gen)
        await db_session.flush()
        (qid,) = await _questions(db_session, world, 1, 1, origin="targeted", generation_id=gen.id)

        body = (
            await client_factory(user).get("/api/study/items", params={"quiz_question_ids": [qid]})
        ).json()

        assert body["quiz_questions"][0]["id"] == qid
        assert body["quiz_questions"][0]["origin"] == "targeted"
        assert body["quiz_questions"][0]["focus_topic"] == "topic"

    async def test_more_than_fifty_ids_is_422(self, make_user, client_factory):
        client = client_factory(await make_user())
        many = [generate_id() for _ in range(51)]
        split = [generate_id() for _ in range(30)]

        assert (
            await client.get("/api/study/items", params={"flashcard_ids": many})
        ).status_code == 422
        assert (
            await client.get(
                "/api/study/items", params={"flashcard_ids": split, "quiz_question_ids": split}
            )
        ).status_code == 422
        exactly = await client.get("/api/study/items", params={"flashcard_ids": many[:50]})
        assert exactly.status_code == 200 and exactly.json() == {
            "flashcards": [],
            "quiz_questions": [],
        }

    async def test_requires_a_caller(self, client_factory):
        assert (await client_factory().get("/api/study/items")).status_code == 401


# ── floor 4: user data is never lost ───────────────────────────────────


async def _targeted_fixture(db, user, world, week=1):
    gen = TargetedGeneration(
        user_id=user.id,
        course_id=world.course.id,
        week=week,
        kind="quiz",
        status="completed",
        requested_count=5,
        created_count=1,
        topics=[],
    )
    db.add(gen)
    await db.flush()
    (qid,) = await _questions(db, world, week, 1, origin="targeted", generation_id=gen.id)
    (cid,) = await _cards(db, world, week, 1)
    card = await db.get(Flashcard, cid)
    card.origin, card.targeted_generation_id, card.focus_topic = "targeted", gen.id, "topic"
    await db.flush()
    return gen, qid, cid


class TestFloor4:
    async def test_targeted_items_survive_pipeline_regeneration(self, make_user, db_session):
        user = await make_user()
        world = await _world(db_session, user)
        _, tq, tc = await _targeted_fixture(db_session, user, world)
        (pq,) = await _questions(db_session, world, 1, 1)
        (pc,) = await _cards(db_session, world, 1, 1)
        await _attempts(db_session, [pq, tq], [False, False])

        await asset_service.save_quiz_questions(
            db_session, world.course.id, 1, world.artifact.id, []
        )
        await asset_service.save_flashcards(db_session, world.course.id, 1, world.artifact.id, [])

        assert (await db_session.get(QuizQuestion, tq)).archived_at is None
        assert (await db_session.get(Flashcard, tc)).archived_at is None
        # The pipeline's own items are archived, never deleted, and keep their history.
        old_q, old_c = await db_session.get(QuizQuestion, pq), await db_session.get(Flashcard, pc)
        assert old_q is not None and old_q.archived_at is not None
        assert old_c is not None and old_c.archived_at is not None
        attempts = await db_session.scalar(
            select(func.count())
            .select_from(QuizAttempt)
            .where(QuizAttempt.quiz_question_id.in_([pq, tq]))
        )
        assert attempts == 2

    async def test_a_regenerated_week_keeps_targeted_items_in_the_plan_pool(
        self, make_user, client_factory, db_session
    ):
        user = await make_user()
        world = await _world(db_session, user)
        _, tq, _ = await _targeted_fixture(db_session, user, world)
        (pq,) = await _questions(db_session, world, 1, 1)
        await _attempts(db_session, [pq, pq, pq], [False] * 3)
        await asset_service.save_quiz_questions(
            db_session, world.course.id, 1, world.artifact.id, []
        )

        body = (
            await client_factory(user).get(
                "/api/study/items", params={"quiz_question_ids": [tq, pq]}
            )
        ).json()

        assert [q["id"] for q in body["quiz_questions"]] == [tq]


class TestAccountDeletion:
    async def test_plans_generations_and_targeted_items_go_with_the_account_only(
        self, make_user, client_factory, db_session, storage
    ):
        alice, bob = await make_user(), await make_user()
        owners = {}
        for user in (alice, bob):
            world, _, _ = await _plan_world(db_session, user)
            gen, tq, tc = await _targeted_fixture(db_session, user, world, week=1)
            plan = await client_factory(user).get("/api/study-plan/tonight")
            assert plan.status_code == 200 and plan.json()["items"]
            owners[user.id] = (gen.id, tq, tc)

        async def count(model, user_id):
            return await db_session.scalar(
                select(func.count()).select_from(model).where(model.user_id == user_id)
            )

        assert await count(StudyPlan, alice.id) == 1
        assert await count(TargetedGeneration, alice.id) == 1

        await account_service.delete_user_account(db_session, alice.id, storage=storage)
        await db_session.flush()

        gen_id, tq, tc = owners[alice.id]
        assert await count(StudyPlan, alice.id) == 0
        assert await count(TargetedGeneration, alice.id) == 0
        assert await db_session.get(QuizQuestion, tq) is None
        assert await db_session.get(Flashcard, tc) is None
        # Bob's rows are untouched.
        gen_id, tq, tc = owners[bob.id]
        assert await count(StudyPlan, bob.id) == 1
        assert await count(TargetedGeneration, bob.id) == 1
        assert await db_session.get(QuizQuestion, tq) is not None
        assert await db_session.get(Flashcard, tc) is not None


# ── plan split (api.usage retention) ───────────────────────────────────


class TestPlanSplit:
    async def test_plan_in_the_first_week_moves_a_signup_to_the_with_plan_arm(
        self, make_user, db_session
    ):
        wk = usage_service.week_start(datetime.now(UTC).date()) - timedelta(weeks=2)
        signup = datetime(wk.year, wk.month, wk.day, 9, tzinfo=UTC)
        planner = await make_user(created_at=signup)
        await make_user(created_at=signup)
        db_session.add(
            StudyPlan(
                user_id=planner.id,
                plan_date=wk + timedelta(days=2),
                minutes=25,
                items=[],
                focus=[],
                algorithm_version=1,
                version=1,
                built_at=signup + timedelta(days=2),
            )
        )
        late = await make_user(created_at=signup)
        db_session.add(
            StudyPlan(
                user_id=late.id,
                plan_date=wk + timedelta(days=9),  # after day 6: does not count
                minutes=25,
                items=[],
                focus=[],
                algorithm_version=1,
                version=1,
                built_at=signup + timedelta(days=9),
            )
        )
        await db_session.flush()

        rows = await usage_service.plan_split_readout(db_session, weeks=4)

        (row,) = [r for r in rows if r["week_start"] == wk.isoformat()]
        assert row["with_plan"]["signups"] == 1
        assert row["without_plan"]["signups"] == 2


# ── cross-user ─────────────────────────────────────────────────────────


class TestCrossUser:
    async def test_bob_sees_nothing_of_alices_engine_state(
        self, make_user, client_factory, db_session
    ):
        alice, bob = await make_user(), await make_user()
        a_world, a_q, a_cards = await _plan_world(db_session, alice)
        b_world = await _world(db_session, bob, code="BOB1")
        (b_q,) = await _questions(db_session, b_world, 1, 1)
        a_client, b_client = client_factory(alice), client_factory(bob)
        with _enqueue_mocked():
            gen = (
                await a_client.post(
                    "/api/weak-spots/targeted",
                    json={"course_id": a_world.course.id, "week": 1, "kind": "quiz"},
                )
            ).json()
            # Bob cannot request practice for Alice's course either.
            hijack = await b_client.post(
                "/api/weak-spots/targeted",
                json={"course_id": a_world.course.id, "week": 1, "kind": "flashcards"},
            )
        a_plan = (await a_client.get("/api/study-plan/tonight")).json()
        assert a_plan["items"]
        a_ids = {i["item_id"] for i in a_plan["items"]} | {q for qs in a_q.values() for q in qs}

        assert hijack.status_code == 404
        assert (await a_client.get(f"/api/weak-spots/targeted/{gen['id']}")).status_code == 200
        assert (await b_client.get(f"/api/weak-spots/targeted/{gen['id']}")).status_code == 404

        b_plan = (await b_client.get("/api/study-plan/tonight")).json()
        assert not ({i["item_id"] for i in b_plan["items"]} & a_ids)
        assert {c["course_id"] for c in b_plan["focus"]} <= {b_world.course.id}

        b_map = (await b_client.get("/api/weak-spots")).json()
        assert [c["course_id"] for c in b_map["courses"]] == [b_world.course.id]
        assert (
            await b_client.get("/api/weak-spots", params={"course_id": a_world.course.id})
        ).json()["courses"] == []

        diag = await b_client.get(
            "/api/weak-spots/diagnostic", params={"course_id": a_world.course.id, "week": 4}
        )
        assert diag.status_code == 404

        items = (
            await b_client.get(
                "/api/study/items",
                params={
                    "flashcard_ids": [*a_cards, a_plan["items"][0]["item_id"]],
                    "quiz_question_ids": [*a_q[1], *a_q[4], b_q],
                },
            )
        ).json()
        assert [q["id"] for q in items["quiz_questions"]] == [b_q]
        assert items["flashcards"] == []

    async def test_a_foreign_item_in_a_stored_plan_is_not_resolved(self, make_user, db_session):
        alice, bob = await make_user(), await make_user()
        a_world = await _world(db_session, alice)
        (a_q,) = await _questions(db_session, a_world, 1, 1)
        plan = StudyPlan(
            user_id=bob.id,
            plan_date=datetime.now(UTC).date(),
            minutes=25,
            items=[
                {
                    "item_type": "quiz",
                    "item_id": a_q,
                    "course_id": a_world.course.id,
                    "course_code": a_world.course.code,
                    "week": 1,
                    "reason": "new",
                    "minutes": 2,
                }
            ],
            focus=[],
            algorithm_version=1,
            version=1,
            built_at=datetime.now(UTC),
        )
        db_session.add(plan)
        await db_session.flush()

        assert await ws.resolve_plan_items(db_session, plan, user_id=bob.id) == []

    async def test_requests_are_rejected_without_a_session(self, client_factory):
        client = client_factory()
        for method, path in (
            ("GET", "/api/weak-spots"),
            ("GET", "/api/weak-spots/diagnostic"),
            ("POST", "/api/weak-spots/targeted"),
            ("GET", "/api/weak-spots/targeted/x"),
            ("GET", "/api/study-plan/tonight"),
            ("POST", "/api/study-plan/tonight/refresh"),
        ):
            assert (await client.request(method, path)).status_code == 401, (method, path)

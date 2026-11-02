"""R-010: `review_items` and `quiz_attempts` carry their own `user_id`.

Both tables used to be owned only by inference (review item -> entity -> owner,
quiz attempt -> question -> course -> owner). They now have a direct, NOT NULL
`user_id`, and every read filters on it. These tests run on real rows with two
users and pin three things:

* neither user can see the other's rows through the API,
* a row written through the API is stamped with the caller,
* account deletion removes the user's rows and nobody else's.

The review items below deliberately point at an entity id that exists nowhere.
Under the old entity-join scoping such a row belonged to nobody; only a direct
`user_id` predicate makes it visible to its owner, so these tests fail if a read
falls back to inferring ownership.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.core.utils import generate_id
from app.models.quiz_attempt import QuizAttempt
from app.models.review_item import ReviewItem
from app.services import account_service

from ._support import seed_course

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _review_item(db_session, user_id: str) -> ReviewItem:
    item = ReviewItem(
        id=generate_id(),
        user_id=user_id,
        review_type="classification_course",
        entity_type="lecture_artifact",
        entity_id=generate_id(),
        payload_json={},
        suggested_values={},
        status="pending",
    )
    db_session.add(item)
    await db_session.flush()
    return item


async def _attempts(db_session, user_id: str, question_ids: list[str], correct: bool) -> None:
    for qid in question_ids:
        db_session.add(
            QuizAttempt(
                id=generate_id(),
                user_id=user_id,
                quiz_question_id=qid,
                selected_answer="x",
                is_correct=correct,
            )
        )
    await db_session.flush()


async def _count(db_session, model, user_id: str) -> int:
    return await db_session.scalar(
        select(func.count()).select_from(model).where(model.user_id == user_id)
    )


class TestReviewItemsAreOwnedDirectly:
    async def test_each_user_lists_only_their_own_items(
        self, client_factory, make_user, db_session
    ):
        alice, bob = await make_user(), await make_user()
        a_item = await _review_item(db_session, alice.id)
        b_item = await _review_item(db_session, bob.id)

        a_ids = {i["id"] for i in (await client_factory(alice).get("/api/review-items")).json()}
        b_ids = {i["id"] for i in (await client_factory(bob).get("/api/review-items")).json()}

        assert a_ids == {a_item.id}
        assert b_ids == {b_item.id}

    async def test_another_users_item_is_a_404_by_id(self, client_factory, make_user, db_session):
        alice, bob = await make_user(), await make_user()
        item = await _review_item(db_session, alice.id)

        assert (await client_factory(alice).get(f"/api/review-items/{item.id}")).status_code == 200
        assert (await client_factory(bob).get(f"/api/review-items/{item.id}")).status_code == 404

    async def test_another_users_item_cannot_be_dismissed(
        self, client_factory, make_user, db_session
    ):
        alice, bob = await make_user(), await make_user()
        item = await _review_item(db_session, alice.id)

        resp = await client_factory(bob).post(f"/api/review-items/{item.id}/dismiss")

        # Deliberately a 400 "not found", not a 404: a foreign item must be
        # indistinguishable from a missing one (no existence oracle). The
        # detail pins the cause -- an "already ..." 400 would be a different bug.
        assert resp.status_code == 400
        detail = resp.json()["detail"].lower()
        assert "not found" in detail and "already" not in detail
        await db_session.refresh(item)
        assert item.status == "pending"


class TestQuizAttemptsAreOwnedDirectly:
    async def test_posted_attempt_is_stamped_with_the_caller(
        self, client_factory, make_user, db_session
    ):
        alice, bob = await make_user(), await make_user()
        seeded = await seed_course(db_session, alice.id)

        resp = await client_factory(alice).post(
            "/api/study/quiz-attempt",
            json={
                "quiz_question_id": seeded.questions[0].id,
                "selected_answer": "A",
                "is_correct": True,
            },
        )

        assert resp.status_code == 201, resp.text
        stored = await db_session.get(QuizAttempt, resp.json()["id"])
        assert stored.user_id == alice.id
        assert await _count(db_session, QuizAttempt, bob.id) == 0

    async def test_rejected_attempt_on_anothers_question_stores_nothing(
        self, client_factory, make_user, db_session
    ):
        alice, bob = await make_user(), await make_user()
        seeded = await seed_course(db_session, alice.id)

        resp = await client_factory(bob).post(
            "/api/study/quiz-attempt",
            json={
                "quiz_question_id": seeded.questions[0].id,
                "selected_answer": "A",
                "is_correct": False,
            },
        )

        assert resp.status_code == 404
        assert await _count(db_session, QuizAttempt, bob.id) == 0
        assert await _count(db_session, QuizAttempt, alice.id) == 0

    async def test_weak_spots_count_only_the_callers_attempts(
        self, client_factory, make_user, db_session
    ):
        """Same course code, same week: one user has failed attempts, one has none."""
        alice, bob = await make_user(), await make_user()
        a = await seed_course(db_session, alice.id, code="OWN101", week=1, quizzes=5)
        b = await seed_course(db_session, bob.id, code="OWN101", week=1, quizzes=5)
        await _attempts(db_session, alice.id, [q.id for q in a.questions], correct=False)

        def week1(body, course_id):
            (course,) = [c for c in body["courses"] if c["course_id"] == course_id]
            return {w["week"]: w for w in course["weeks"]}[1]

        a_body = (await client_factory(alice).get("/api/weak-spots")).json()
        b_body = (await client_factory(bob).get("/api/weak-spots")).json()

        assert week1(a_body, a.course.id)["status"] == "weak"
        assert week1(b_body, b.course.id)["status"] == "unknown"
        assert a.course.id not in {c["course_id"] for c in b_body["courses"]}

    async def test_exam_progress_ignores_another_users_attempts(
        self, client_factory, make_user, db_session
    ):
        alice, bob = await make_user(), await make_user()
        a = await seed_course(db_session, alice.id, code="OWN202", week=3, quizzes=4)
        b = await seed_course(db_session, bob.id, code="OWN202", week=3, quizzes=4)
        await _attempts(db_session, alice.id, [q.id for q in a.questions], correct=True)
        # A row stamped with Alice but sitting on Bob's question: Bob's progress
        # must still not count it. Only a direct `user_id` predicate excludes
        # it; the question -> course join alone would include it.
        await _attempts(db_session, alice.id, [q.id for q in b.questions], correct=True)

        body = {
            "course_code": "OWN202",
            "title": "Midterm",
            "exam_date": (datetime.now(UTC) + timedelta(days=14)).isoformat(),
            "weeks_scope": [3],
            "target_mastery_pct": 80,
        }
        progress = {}
        for who in (alice, bob):
            client = client_factory(who)
            created = await client.post("/api/exams", json=body)
            assert created.status_code == 201, created.text
            resp = await client.get(f"/api/exams/{created.json()['id']}")
            assert resp.status_code == 200, resp.text
            progress[who.id] = resp.json()

        assert progress[alice.id]["quiz_total"] == 4
        assert progress[bob.id]["quiz_total"] == 0


class TestAccountDeletionRemovesOwnedRows:
    async def test_deletes_the_users_rows_and_leaves_the_others(
        self, make_user, db_session, storage
    ):
        victim, keeper = await make_user(), await make_user()
        v = await seed_course(db_session, victim.id, code="DEL301", quizzes=2)
        k = await seed_course(db_session, keeper.id, code="DEL301", quizzes=2)
        for uid, world in ((victim.id, v), (keeper.id, k)):
            await _review_item(db_session, uid)
            await _attempts(db_session, uid, [q.id for q in world.questions], correct=True)
        assert await _count(db_session, ReviewItem, victim.id) == 1
        assert await _count(db_session, QuizAttempt, victim.id) == 2

        await account_service.delete_user_account(db_session, victim.id, storage=storage)
        await db_session.flush()

        assert await _count(db_session, ReviewItem, victim.id) == 0
        assert await _count(db_session, QuizAttempt, victim.id) == 0
        assert await _count(db_session, ReviewItem, keeper.id) == 1
        assert await _count(db_session, QuizAttempt, keeper.id) == 2

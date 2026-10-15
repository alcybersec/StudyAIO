"""Study-item CRUD (GL#48) and upload placement (GL#49) against real Postgres.

Every state claim is checked in the database, not just in the status line: an
edit must archive the original (floor 4) and a foreign id must leave the other
user's rows untouched (floor 1).
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import func, select

from app.models.artifact import LectureArtifact
from app.models.course import Course
from app.models.flashcard import Flashcard
from app.models.flashcard_review import FlashcardReview
from app.models.quiz import QuizQuestion
from app.models.review_item import ReviewItem

from ._support import make_docx, make_pdf, seed_course

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _cards(db, course_id):
    return (
        (await db.execute(select(Flashcard).where(Flashcard.course_id == course_id)))
        .scalars()
        .all()
    )


async def _quizzes(db, course_id):
    return (
        (await db.execute(select(QuizQuestion).where(QuizQuestion.course_id == course_id)))
        .scalars()
        .all()
    )


class TestFlashcardCrud:
    async def test_edit_archives_original_and_inserts_user_copy(
        self, client_factory, make_user, db_session
    ):
        user = await make_user()
        world = await seed_course(db_session, user.id, flashcards=1, quizzes=0)
        card = world.flashcards[0]
        original_front = card.front
        db_session.add(
            FlashcardReview(
                user_id=user.id,
                flashcard_id=card.id,
                ease_factor=2.1,
                interval_days=9,
                repetition_count=4,
                next_review_at=datetime.now(UTC) + timedelta(days=9),
            )
        )
        await db_session.flush()

        resp = await client_factory(user).patch(
            f"/api/assets/flashcards/{card.id}", json={"front": "  New front  "}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["id"] != card.id
        assert body["front"] == "New front" and body["origin"] == "user"
        assert body["back"] == card.back  # unchanged field carried over

        rows = {c.id: c for c in await _cards(db_session, world.course.id)}
        assert set(rows) == {card.id, body["id"]}  # prior version kept
        await db_session.refresh(rows[card.id])
        assert rows[card.id].archived_at is not None
        assert rows[card.id].front == original_front
        new = rows[body["id"]]
        assert new.archived_at is None and new.origin == "user"
        assert (new.course_id, new.week, new.source_artifact_id) == (
            card.course_id,
            card.week,
            card.source_artifact_id,
        )
        old_review = (
            await db_session.execute(
                select(FlashcardReview).where(FlashcardReview.flashcard_id == card.id)
            )
        ).scalar_one()
        new_review = (
            await db_session.execute(
                select(FlashcardReview).where(FlashcardReview.flashcard_id == new.id)
            )
        ).scalar_one()
        assert old_review.repetition_count == 4  # history stays on the original
        assert (new_review.ease_factor, new_review.interval_days, new_review.repetition_count) == (
            2.1,
            9,
            4,
        )

    async def test_edit_with_no_fields_is_422_and_changes_nothing(
        self, client_factory, make_user, db_session
    ):
        user = await make_user()
        world = await seed_course(db_session, user.id, flashcards=1, quizzes=0)
        resp = await client_factory(user).patch(
            f"/api/assets/flashcards/{world.flashcards[0].id}", json={}
        )
        assert resp.status_code == 422
        rows = await _cards(db_session, world.course.id)
        assert len(rows) == 1 and rows[0].archived_at is None

    async def test_delete_archives_not_removes(self, client_factory, make_user, db_session):
        user = await make_user()
        world = await seed_course(db_session, user.id, flashcards=1, quizzes=0)
        card = world.flashcards[0]
        client = client_factory(user)
        assert (await client.delete(f"/api/assets/flashcards/{card.id}")).status_code == 204
        await db_session.refresh(card)
        assert card.archived_at is not None
        assert len(await _cards(db_session, world.course.id)) == 1  # row still there
        # already archived -> plain 404
        assert (await client.delete(f"/api/assets/flashcards/{card.id}")).status_code == 404

    async def test_add_uses_newest_artifact_for_the_week(
        self, client_factory, make_user, db_session
    ):
        user = await make_user()
        world = await seed_course(
            db_session, user.id, code="NET101", week=3, flashcards=0, quizzes=0
        )
        resp = await client_factory(user).post(
            "/api/assets/flashcards",
            json={"course_code": "NET101", "week": 3, "front": "F", "back": "B", "tags": ["x"]},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["origin"] == "user" and body["source_artifact_id"] == world.artifact.id
        row = (await _cards(db_session, world.course.id))[0]
        assert (row.week, row.origin, row.archived_at) == (3, "user", None)

    async def test_add_with_explicit_source_artifact(self, client_factory, make_user, db_session):
        user = await make_user()
        world = await seed_course(db_session, user.id, week=3, flashcards=0, quizzes=0)
        resp = await client_factory(user).post(
            "/api/assets/flashcards",
            json={
                "course_code": "NET101",
                "week": 3,
                "front": "F",
                "back": "B",
                "source_artifact_id": world.artifact.id,
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["source_artifact_id"] == world.artifact.id

    async def test_add_for_week_without_lecture_is_409(self, client_factory, make_user, db_session):
        user = await make_user()
        world = await seed_course(db_session, user.id, week=3, flashcards=0, quizzes=0)
        resp = await client_factory(user).post(
            "/api/assets/flashcards",
            json={"course_code": "NET101", "week": 7, "front": "F", "back": "B"},
        )
        assert resp.status_code == 409
        assert "no_source_artifact" in resp.text
        assert await _cards(db_session, world.course.id) == []

    async def test_add_unknown_course_is_404_and_blank_text_422(
        self, client_factory, make_user, db_session
    ):
        user = await make_user()
        await seed_course(db_session, user.id, flashcards=0, quizzes=0)
        client = client_factory(user)
        r = await client.post(
            "/api/assets/flashcards",
            json={"course_code": "NOPE9", "week": 1, "front": "F", "back": "B"},
        )
        assert r.status_code == 404
        r = await client.post(
            "/api/assets/flashcards",
            json={"course_code": "NET101", "week": 3, "front": "   ", "back": "B"},
        )
        assert r.status_code == 422

    async def test_add_with_foreign_source_artifact_is_refused(
        self, client_factory, make_user, db_session
    ):
        alice, bob = await make_user(), await make_user()
        await seed_course(db_session, alice.id, week=3, flashcards=0, quizzes=0)
        theirs = await seed_course(db_session, bob.id, week=3, flashcards=0, quizzes=0)
        resp = await client_factory(alice).post(
            "/api/assets/flashcards",
            json={
                "course_code": "NET101",
                "week": 3,
                "front": "F",
                "back": "B",
                "source_artifact_id": theirs.artifact.id,
            },
        )
        assert resp.status_code in (404, 409, 422), resp.text
        assert await _cards(db_session, theirs.course.id) == []

    async def test_cross_user_edit_and_delete_are_404_and_untouched(
        self, client_factory, make_user, db_session
    ):
        alice, bob = await make_user(), await make_user()
        theirs = await seed_course(db_session, bob.id, flashcards=1, quizzes=0)
        card = theirs.flashcards[0]
        before = (card.front, card.back, card.origin)
        client = client_factory(alice)

        assert (
            await client.patch(f"/api/assets/flashcards/{card.id}", json={"front": "pwned"})
        ).status_code == 404
        assert (await client.delete(f"/api/assets/flashcards/{card.id}")).status_code == 404

        await db_session.refresh(card)
        assert card.archived_at is None
        assert (card.front, card.back, card.origin) == before
        assert len(await _cards(db_session, theirs.course.id)) == 1  # no copy minted


class TestQuizCrud:
    async def test_edit_archives_original_and_inserts_user_copy(
        self, client_factory, make_user, db_session
    ):
        user = await make_user()
        world = await seed_course(db_session, user.id, flashcards=0, quizzes=1)
        q = world.questions[0]  # multiple choice, options A-D
        original_question = q.question
        resp = await client_factory(user).patch(
            f"/api/assets/quiz/{q.id}", json={"question": "Reworded?", "correct_answer": "B"}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["id"] != q.id and body["origin"] == "user" and body["correct_answer"] == "B"
        assert body["options_json"] == ["A", "B", "C", "D"]

        await db_session.refresh(q)
        assert q.archived_at is not None and q.correct_answer == "A"
        assert q.question == original_question
        assert len(await _quizzes(db_session, world.course.id)) == 2

    async def test_edit_to_incoherent_answer_is_422_and_nothing_archived(
        self, client_factory, make_user, db_session
    ):
        user = await make_user()
        world = await seed_course(db_session, user.id, flashcards=0, quizzes=1)
        q = world.questions[0]
        resp = await client_factory(user).patch(
            f"/api/assets/quiz/{q.id}", json={"correct_answer": "not an option"}
        )
        assert resp.status_code == 422
        await db_session.refresh(q)
        assert q.archived_at is None
        assert len(await _quizzes(db_session, world.course.id)) == 1

    async def test_delete_archives_not_removes(self, client_factory, make_user, db_session):
        user = await make_user()
        world = await seed_course(db_session, user.id, flashcards=0, quizzes=1)
        q = world.questions[0]
        assert (await client_factory(user).delete(f"/api/assets/quiz/{q.id}")).status_code == 204
        await db_session.refresh(q)
        assert q.archived_at is not None
        assert len(await _quizzes(db_session, world.course.id)) == 1

    async def test_add_multiple_choice_and_short_answer(
        self, client_factory, make_user, db_session
    ):
        user = await make_user()
        world = await seed_course(db_session, user.id, week=3, flashcards=0, quizzes=0)
        client = client_factory(user)
        mc = await client.post(
            "/api/assets/quiz",
            json={
                "course_code": "NET101",
                "week": 3,
                "question_type": "multiple_choice",
                "question": "Q?",
                "options": ["x", "y", "z"],
                "correct_answer": "y",
            },
        )
        sa = await client.post(
            "/api/assets/quiz",
            json={
                "course_code": "NET101",
                "week": 3,
                "question_type": "short_answer",
                "question": "Q2?",
                "correct_answer": "free text",
            },
        )
        assert mc.status_code == 201 and sa.status_code == 201, (mc.text, sa.text)
        rows = await _quizzes(db_session, world.course.id)
        assert {r.question_type for r in rows} == {"multiple_choice", "short_answer"}
        assert all(r.origin == "user" and r.source_artifact_id == world.artifact.id for r in rows)

    async def test_add_validation(self, client_factory, make_user, db_session):
        user = await make_user()
        world = await seed_course(db_session, user.id, week=3, flashcards=0, quizzes=0)
        client = client_factory(user)
        base = {"course_code": "NET101", "week": 3, "question": "Q?"}
        bad = [
            {
                **base,
                "question_type": "multiple_choice",
                "options": ["only"],
                "correct_answer": "only",
            },
            {
                **base,
                "question_type": "multiple_choice",
                "options": ["a", "b"],
                "correct_answer": "c",
            },
            {**base, "question_type": "short_answer", "options": ["a", "b"], "correct_answer": "a"},
            {**base, "question_type": "essay", "correct_answer": "a"},
        ]
        for payload in bad:
            assert (await client.post("/api/assets/quiz", json=payload)).status_code == 422, payload
        assert await _quizzes(db_session, world.course.id) == []

    async def test_add_for_week_without_lecture_is_409(self, client_factory, make_user, db_session):
        user = await make_user()
        await seed_course(db_session, user.id, week=3, flashcards=0, quizzes=0)
        resp = await client_factory(user).post(
            "/api/assets/quiz",
            json={
                "course_code": "NET101",
                "week": 9,
                "question_type": "short_answer",
                "question": "Q?",
                "correct_answer": "a",
            },
        )
        assert resp.status_code == 409 and "no_source_artifact" in resp.text

    async def test_cross_user_edit_and_delete_are_404_and_untouched(
        self, client_factory, make_user, db_session
    ):
        alice, bob = await make_user(), await make_user()
        theirs = await seed_course(db_session, bob.id, flashcards=0, quizzes=1)
        q = theirs.questions[0]
        original = q.question
        client = client_factory(alice)
        assert (
            await client.patch(f"/api/assets/quiz/{q.id}", json={"question": "pwned"})
        ).status_code == 404
        assert (await client.delete(f"/api/assets/quiz/{q.id}")).status_code == 404
        await db_session.refresh(q)
        assert q.archived_at is None and q.question == original
        assert len(await _quizzes(db_session, theirs.course.id)) == 1

    async def test_unauthenticated_is_rejected(self, client_factory, make_user, db_session):
        user = await make_user()
        world = await seed_course(db_session, user.id, flashcards=1, quizzes=0)
        resp = await client_factory().delete(f"/api/assets/flashcards/{world.flashcards[0].id}")
        assert resp.status_code in (401, 403)
        await db_session.refresh(world.flashcards[0])
        assert world.flashcards[0].archived_at is None


@pytest.fixture
def dispatched():
    run = MagicMock(return_value=SimpleNamespace(id="task-1"))
    resume = MagicMock(return_value=SimpleNamespace(id="task-2"))
    with (
        patch("app.api.uploads.run_pipeline", run),
        patch("app.api.uploads.resume_pipeline", resume),
    ):
        yield SimpleNamespace(run=run, resume=resume)


async def _artifact(db, artifact_id):
    return (
        await db.execute(select(LectureArtifact).where(LectureArtifact.id == artifact_id))
    ).scalar_one()


class TestUploadPlacement:
    async def test_placed_upload_lands_in_course_week_and_skips_classify(
        self, client_factory, make_user, db_session, dispatched
    ):
        user = await make_user()
        course = Course(id="c" * 36, code="NET101", name="Networks", user_id=user.id)
        db_session.add(course)
        await db_session.flush()

        resp = await client_factory(user).post(
            "/api/uploads?course_code=net101&week=4",
            files={"file": ("any-name.pdf", make_pdf(), "application/pdf")},
        )
        assert resp.status_code == 201, resp.text
        artifact = await _artifact(db_session, resp.json()["artifact_id"])
        assert (artifact.course_id, artifact.week, artifact.status) == (course.id, 4, "classified")
        dispatched.run.assert_not_called()
        dispatched.resume.assert_called_once()
        assert dispatched.resume.call_args.kwargs["from_stage"] == "extract"
        assert dispatched.resume.call_args.kwargs["user_id"] == user.id
        reviews = await db_session.execute(
            select(func.count()).select_from(ReviewItem).where(ReviewItem.entity_id == artifact.id)
        )
        assert reviews.scalar_one() == 0
        # case-insensitive match reused the course rather than minting a second
        n = await db_session.execute(
            select(func.count()).select_from(Course).where(Course.user_id == user.id)
        )
        assert n.scalar_one() == 1

    async def test_placement_creates_missing_course_for_caller(
        self, client_factory, make_user, db_session, dispatched
    ):
        user = await make_user()
        resp = await client_factory(user).post(
            "/api/uploads?course_code=NEW200&week=1",
            files={"file": ("a.pdf", make_pdf(), "application/pdf")},
        )
        assert resp.status_code == 201, resp.text
        artifact = await _artifact(db_session, resp.json()["artifact_id"])
        course = (
            await db_session.execute(select(Course).where(Course.id == artifact.course_id))
        ).scalar_one()
        assert (course.code, course.user_id) == ("NEW200", user.id)

    async def test_partial_or_invalid_params_are_422_and_store_nothing(
        self, client_factory, make_user, db_session, dispatched
    ):
        user = await make_user()
        client = client_factory(user)
        for qs in (
            "course_code=NET101",
            "week=3",
            "course_code=NET101&week=0",
            "course_code=NET101&week=53",
        ):
            resp = await client.post(
                f"/api/uploads?{qs}",
                files={"file": ("a.pdf", make_pdf(), "application/pdf")},
            )
            assert resp.status_code == 422, (qs, resp.text)
        count = await db_session.execute(
            select(func.count())
            .select_from(LectureArtifact)
            .where(LectureArtifact.user_id == user.id)
        )
        assert count.scalar_one() == 0
        dispatched.run.assert_not_called()
        dispatched.resume.assert_not_called()

    async def test_without_placement_routes_through_ai_from_ingest(
        self, client_factory, make_user, db_session, dispatched
    ):
        user = await make_user()
        resp = await client_factory(user).post(
            "/api/uploads", files={"file": ("a.pdf", make_pdf(), "application/pdf")}
        )
        artifact = await _artifact(db_session, resp.json()["artifact_id"])
        assert artifact.course_id is None and artifact.week is None
        dispatched.run.assert_called_once()
        dispatched.resume.assert_not_called()

    async def test_duplicate_ignores_placement_and_stays_per_user(
        self, client_factory, make_user, db_session, dispatched
    ):
        a, b = await make_user(), await make_user()
        content = make_pdf()
        first = await client_factory(a).post(
            "/api/uploads?course_code=NET101&week=2",
            files={"file": ("w.pdf", content, "application/pdf")},
        )
        again = await client_factory(a).post(
            "/api/uploads?course_code=OTHER1&week=9",
            files={"file": ("w.pdf", content, "application/pdf")},
        )
        assert again.json()["status"] == "duplicate"
        assert again.json()["artifact_id"] == first.json()["artifact_id"]
        artifact = await _artifact(db_session, first.json()["artifact_id"])
        assert artifact.week == 2  # the duplicate's placement did not move it
        assert dispatched.resume.call_count == 1

        other = await client_factory(b).post(
            "/api/uploads?course_code=NET101&week=2",
            files={"file": ("w.pdf", content, "application/pdf")},
        )
        assert other.json()["status"] == "processing"
        assert other.json()["artifact_id"] != first.json()["artifact_id"]
        theirs = await _artifact(db_session, other.json()["artifact_id"])
        course = (
            await db_session.execute(select(Course).where(Course.id == theirs.course_id))
        ).scalar_one()
        assert course.user_id == b.id  # placed into B's course, not A's

    async def test_batch_placement_applies_to_every_file(
        self, client_factory, make_user, db_session, dispatched
    ):
        user = await make_user()
        docx_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        resp = await client_factory(user).post(
            "/api/uploads/batch?course_code=NET101&week=5",
            files=[
                ("files", ("a.pdf", make_pdf(), "application/pdf")),
                ("files", ("b.docx", make_docx(), docx_type)),
            ],
        )
        assert resp.status_code in (200, 201), resp.text
        rows = (
            (
                await db_session.execute(
                    select(LectureArtifact).where(LectureArtifact.user_id == user.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 2 and {r.week for r in rows} == {5}
        assert len({r.course_id for r in rows}) == 1
        assert dispatched.resume.call_count == 2 and dispatched.run.call_count == 0
        half = await client_factory(user).post(
            "/api/uploads/batch?week=5",
            files=[("files", ("c.pdf", make_pdf(["other"]), "application/pdf"))],
        )
        assert half.status_code == 422

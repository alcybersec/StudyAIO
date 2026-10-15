"""Floors 1 and 4 for user-authored study items and explicit upload placement.

M33-S3-SAFETY-059 over backend ``3c1ef9c`` (GL#48, GL#49). Pins, run through the
real routes and services over :class:`tests.safety._minidb.MiniDB`, so a dropped
owner predicate changes the answer instead of being masked by a mock:

Floor 1
* ``PATCH``/``DELETE /api/assets/flashcards|quiz/{id}`` on another user's item
  answers the same 404 as a missing id and changes nothing of theirs;
* ``POST /api/assets/flashcards|quiz`` cannot land in another user's course
  (by code) nor hang off another user's lecture (by ``source_artifact_id``);
* ``course_service.get_or_create_course`` (the upload placement path) never
  returns another user's course, even with the same code in another case; it
  creates the caller's own.

Floor 4
* an edit archives the original with its AI text intact and inserts a copy;
  the original's review row stays and the copy gets the caller's own schedule;
* a delete is a soft delete: the row and its review history are still there.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from tests.safety._minidb import MiniDB, MiniSession

USER_A = "floor1-items-user-a"
USER_B = "floor1-items-user-b"
MISSING = "floor1-items-missing-id"


class _Session(MiniSession):
    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None

    async def refresh(self, *_a: Any, **_k: Any) -> None:
        return None


def _seed(db: MiniDB, owner: str) -> dict[str, str]:
    from app.models.artifact import LectureArtifact
    from app.models.course import Course
    from app.models.flashcard import Flashcard
    from app.models.flashcard_review import FlashcardReview
    from app.models.quiz import QuizQuestion

    tag = owner.rsplit("-", 1)[-1]
    course = Course(id=f"course-{tag}", user_id=owner, code=f"CS{tag.upper()}", name="c")
    artifact = LectureArtifact(
        id=f"artifact-{tag}",
        user_id=owner,
        course_id=course.id,
        week=1,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    card = Flashcard(
        id=f"card-{tag}",
        course_id=course.id,
        week=1,
        front=f"ai-front-{tag}",
        back=f"ai-back-{tag}",
        tags=[],
        source_artifact_id=artifact.id,
        source_page_ref=3,
        generation_version=1,
        origin="ai",
    )
    review = FlashcardReview(
        id=f"review-{tag}",
        user_id=owner,
        flashcard_id=card.id,
        ease_factor=2.1,
        interval_days=6,
        repetition_count=2,
        next_review_at=datetime(2026, 2, 1, tzinfo=UTC),
    )
    question = QuizQuestion(
        id=f"quiz-{tag}",
        course_id=course.id,
        week=1,
        question_type="short_answer",
        question=f"ai-question-{tag}",
        correct_answer="42",
        explanation="",
        source_artifact_id=artifact.id,
        source_page_ref=3,
        generation_version=1,
        origin="ai",
    )
    for obj in (course, artifact, card, review, question):
        db.add(obj)
    return {
        "course": course.id,
        "code": course.code,
        "artifact": artifact.id,
        "flashcard": card.id,
        "quiz": question.id,
    }


@pytest.fixture
def world(async_client, make_user):
    """``async_client`` acting as USER_A over a MiniDB holding A's and B's rows."""
    from app.api.deps import get_current_user_or_default
    from app.core.database import get_session
    from app.main import app

    db = MiniDB()
    ids = {USER_A: _seed(db, USER_A), USER_B: _seed(db, USER_B)}
    caller = make_user(id=USER_A, role="user", tier="free")

    async def session_override():
        yield _Session(db)

    async def user_override():
        return caller

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_current_user_or_default] = user_override
    return async_client, db, ids


def _snapshot(db: MiniDB, owner_ids: dict[str, str]) -> dict[str, Any]:
    """Every column of the owner's item and review rows, for an unchanged-check."""
    keep = {owner_ids["flashcard"], owner_ids["quiz"]}
    out = {}
    for table in ("flashcards", "quiz_questions", "flashcard_reviews"):
        for obj in db.rows[table]:
            key = getattr(obj, "flashcard_id", None) or obj.id
            if key in keep:
                out[(table, obj.id)] = dict(db.row(obj))
    return out


_ITEM_PATHS = {
    "flashcard": ("/api/assets/flashcards", {"front": "edited"}),
    "quiz": ("/api/assets/quiz", {"question": "edited"}),
}


# ── floor 1: edits and deletes of another user's item ─────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", sorted(_ITEM_PATHS))
@pytest.mark.parametrize("method", ["patch", "delete"])
async def test_floor1_foreign_item_edit_or_delete_is_404_like_missing(world, kind, method):
    client, db, ids = world
    path, body = _ITEM_PATHS[kind]
    before = _snapshot(db, ids[USER_B])
    sizes = {t: len(db.rows[t]) for t in ("flashcards", "quiz_questions", "flashcard_reviews")}

    def call(item_id: str):
        url = f"{path}/{item_id}"
        return client.patch(url, json=body) if method == "patch" else client.delete(url)

    foreign = await call(ids[USER_B][kind])
    missing = await call(MISSING)

    assert foreign.status_code == 404, foreign.text
    assert (foreign.status_code, foreign.json()) == (missing.status_code, missing.json())
    assert _snapshot(db, ids[USER_B]) == before, "user B's item or review changed"
    assert {t: len(db.rows[t]) for t in sizes} == sizes, "a row was written"


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", sorted(_ITEM_PATHS))
async def test_floor1_create_cannot_target_a_foreign_course_or_lecture(world, kind):
    client, db, ids = world
    path, _ = _ITEM_PATHS[kind]
    extra = (
        {"front": "f", "back": "b"}
        if kind == "flashcard"
        else {"question_type": "short_answer", "question": "q", "correct_answer": "a"}
    )
    table = "flashcards" if kind == "flashcard" else "quiz_questions"
    size = len(db.rows[table])

    by_code = await client.post(path, json={"course_code": ids[USER_B]["code"], "week": 1, **extra})
    by_artifact = await client.post(
        path,
        json={
            "course_code": ids[USER_A]["code"],
            "week": 1,
            "source_artifact_id": ids[USER_B]["artifact"],
            **extra,
        },
    )

    assert by_code.status_code == 404, by_code.text
    assert by_artifact.status_code == 404, by_artifact.text
    assert len(db.rows[table]) == size, "a foreign-targeted item was written"

    own = await client.post(path, json={"course_code": ids[USER_A]["code"], "week": 1, **extra})
    assert own.status_code == 201, own.text
    created = [o for o in db.rows[table] if o.origin == "user"]
    assert [(o.course_id, o.source_artifact_id) for o in created] == [
        (ids[USER_A]["course"], ids[USER_A]["artifact"])
    ]


# ── floor 4: edit and delete keep the original ────────────────────────


@pytest.mark.asyncio
async def test_floor4_flashcard_edit_archives_the_original_and_keeps_its_history(world):
    client, db, ids = world
    own = ids[USER_A]["flashcard"]

    resp = await client.patch(f"/api/assets/flashcards/{own}", json={"front": "edited"})

    assert resp.status_code == 200, resp.text
    original = db.get(db.models["flashcards"], own)
    assert original is not None, "the edited flashcard row is gone"
    assert original.archived_at is not None
    assert (original.front, original.back, original.origin) == ("ai-front-a", "ai-back-a", "ai")
    copy = db.get(db.models["flashcards"], resp.json()["id"])
    assert copy is not None and copy.id != own and copy.origin == "user"
    reviews = {r.flashcard_id: r for r in db.rows["flashcard_reviews"]}
    assert own in reviews, "the original's review history was dropped"
    assert reviews[copy.id].user_id == USER_A
    assert reviews[copy.id].interval_days == reviews[own].interval_days


@pytest.mark.asyncio
async def test_floor4_quiz_edit_archives_the_original(world):
    client, db, ids = world
    own = ids[USER_A]["quiz"]

    resp = await client.patch(f"/api/assets/quiz/{own}", json={"question": "edited"})

    assert resp.status_code == 200, resp.text
    original = db.get(db.models["quiz_questions"], own)
    assert original is not None and original.archived_at is not None
    assert original.question == "ai-question-a"
    assert resp.json()["id"] != own


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", sorted(_ITEM_PATHS))
async def test_floor4_item_delete_is_a_soft_delete(world, kind):
    client, db, ids = world
    path, _ = _ITEM_PATHS[kind]
    own = ids[USER_A][kind]
    table = "flashcards" if kind == "flashcard" else "quiz_questions"
    reviews = len(db.rows["flashcard_reviews"])

    resp = await client.delete(f"{path}/{own}")

    assert resp.status_code == 204, resp.text
    row = db.get(db.models[table], own)
    assert row is not None, f"DELETE {path} removed the row; floor 4 wants it archived"
    assert row.archived_at is not None
    assert len(db.rows["flashcard_reviews"]) == reviews, "review history was dropped"


# ── floor 1: upload placement resolves only the caller's course ───────


@pytest.mark.asyncio
async def test_floor1_upload_placement_never_resolves_a_foreign_course():
    from app.services import course_service

    db = MiniDB()
    ids = {USER_A: _seed(db, USER_A), USER_B: _seed(db, USER_B)}
    session = _Session(db)

    with patch.object(course_service, "check_course_quota", AsyncMock()) as quota:
        same = await course_service.get_or_create_course(
            session, ids[USER_A]["code"].lower(), user_id=USER_A, tier="free"
        )
        other = await course_service.get_or_create_course(
            session, ids[USER_B]["code"].lower(), user_id=USER_A, tier="free"
        )

    assert same.id == ids[USER_A]["course"], "case-insensitive match missed the caller's course"
    assert other.id != ids[USER_B]["course"], "placement resolved another user's course"
    assert other.user_id == USER_A and other.code == ids[USER_B]["code"]
    assert quota.await_args.args[1] == USER_A, "the new course's quota was checked for someone else"

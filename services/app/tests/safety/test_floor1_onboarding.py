"""Floor 1 for first-run onboarding, ``GET`` and ``PATCH /api/onboarding``.

M34-S3-BACKEND-012 (``api.onboarding v1``). The status is derived on read from
five facts about the caller, and one preference is stored on the caller's
``users`` row. Each fact is a cross-table read, so one dropped predicate would
light one user's checklist from another user's activity:

* every statement the routes run carries the caller's id;
* ``quiz_attempts`` has no ``user_id``, so its branch must be scoped through
  ``quiz_questions`` to ``courses.user_id`` (contracts-safety review, M34);
* ``users`` is unowned to the route sweep, so ``PATCH`` must be keyed on
  ``users.id == caller``, and must leave every other user's row alone.

The behavioural pins run the real routes and services over
:class:`tests.safety._minidb.MiniDB` with a second user who has done
everything, so a dropped predicate changes the answer. Each foreign fact has a
positive control (the same fact for the caller does move the status), so no
pin passes because the fact is never read.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.dialects import postgresql

from tests.safety._minidb import MiniDB, MiniSession
from tests.safety._tenant import tables_in

USER_A = "floor1-onboarding-user-a"
USER_B = "floor1-onboarding-user-b"


class _Session(MiniSession):
    """MiniSession that records every statement and answers commit."""

    def __init__(self, db: MiniDB, log: list) -> None:
        super().__init__(db)
        self.log = log

    async def execute(self, statement: Any, *a: Any, **k: Any):
        self.log.append(statement)
        return await super().execute(statement, *a, **k)

    async def scalar(self, statement: Any, *a: Any, **k: Any):
        self.log.append(statement)
        return await super().scalar(statement, *a, **k)

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


def _fact(db: MiniDB, owner: str, fact: str) -> None:
    """Give ``owner`` one onboarding fact (plus what it needs to exist)."""
    from app.models.artifact import LectureArtifact
    from app.models.course import Course
    from app.models.flashcard import Flashcard
    from app.models.flashcard_review import FlashcardReview
    from app.models.quiz import QuizQuestion
    from app.models.quiz_attempt import QuizAttempt
    from app.models.summary import Summary
    from app.models.usage_event import UsageEvent

    tag = f"{owner.rsplit('-', 1)[-1]}-{fact}"
    course = Course(id=f"course-{tag}", user_id=owner, code=f"C{tag}".upper(), name="c")
    rows: list[Any] = [course]
    if fact == "artifact":
        rows.append(
            LectureArtifact(
                id=f"art-{tag}", user_id=owner, course_id=course.id, sha256=f"sha-{tag}"
            )
        )
    elif fact == "summary":
        rows.append(Summary(id=f"sum-{tag}", course_id=course.id, week=1, content_md="s"))
    elif fact == "summary_viewed":
        rows.append(UsageEvent(id=f"ev-{tag}", user_id=owner, event="summary_viewed"))
    elif fact == "flashcard_review":
        card = Flashcard(id=f"card-{tag}", course_id=course.id, front="f", back="b")
        rows += [card, FlashcardReview(id=f"rev-{tag}", user_id=owner, flashcard_id=card.id)]
    elif fact == "quiz_attempt":
        question = QuizQuestion(id=f"q-{tag}", course_id=course.id, question="q")
        rows += [
            question,
            QuizAttempt(
                id=f"att-{tag}",
                quiz_question_id=question.id,
                selected_answer="a",
                is_correct=True,
            ),
        ]
    else:  # pragma: no cover - a typo in a parametrize id
        raise AssertionError(fact)
    for obj in rows:
        db.add(obj)


EVERY_FACT = ("artifact", "summary", "summary_viewed", "flashcard_review", "quiz_attempt")


@pytest.fixture
def world(async_client, make_user):
    """``async_client`` acting as USER_A; USER_B has done every onboarding step."""
    from app.api.deps import get_current_user_or_default
    from app.core.database import get_session
    from app.main import app
    from app.models.user import User

    db = MiniDB()
    caller = make_user(id=USER_A, email="a@example.test", username="a")
    for uid, state in ((USER_A, "auto"), (USER_B, "pinned")):
        db.add(
            User(
                id=uid,
                email=f"{uid}@example.test",
                username=uid,
                hashed_password="x",
                onboarding_checklist=state,
            )
        )
    for fact in EVERY_FACT:
        _fact(db, USER_B, fact)
    log: list = []

    async def session_override():
        yield _Session(db, log)

    async def user_override():
        return caller

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_current_user_or_default] = user_override
    return async_client, db, log


def _compiled(statement: Any) -> tuple[str, dict]:
    c = statement.compile(dialect=postgresql.dialect())
    return str(c), dict(c.params)


# ── GET ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_floor1_onboarding_get_ignores_another_users_activity(world):
    """With nothing of their own, the caller is ``new`` though the other user is ``done``."""
    client, _db, _log = world
    r = await client.get("/api/onboarding")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["phase"] == "new"
    assert body["summary_target"] is None
    assert body["steps"] == {"upload": "active", "summary": "locked", "check_in": "locked"}
    assert body["checklist"] == "auto", "the preference was read from another user's row"


#: (fact, the caller's baseline facts, the field it moves, foreign value, own value)
FACT_CASES = [
    ("artifact", (), "phase", "new", "processing"),
    ("summary", (), "phase", "new", "has_summary"),
    ("summary_viewed", ("summary",), "summary_step", "active", "done"),
    ("flashcard_review", ("summary",), "phase", "has_summary", "done"),
    ("quiz_attempt", ("summary",), "phase", "has_summary", "done"),
]


def _field(body: dict, field: str) -> str:
    return body["steps"]["summary"] if field == "summary_step" else body[field]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fact", "baseline", "field", "foreign", "own"), FACT_CASES, ids=[c[0] for c in FACT_CASES]
)
async def test_floor1_onboarding_each_fact_is_the_callers_own(
    world, fact, baseline, field, foreign, own
):
    """Another user's fact never moves the caller's status; the caller's own does.

    ``quiz_attempt`` is the branch with no ``user_id`` on its table: an
    ``EXISTS`` over ``quiz_attempts`` without the ``courses.user_id`` join would
    report the caller ``done`` from the other user's answer.
    """
    client, db, _log = world
    for base in baseline:
        _fact(db, USER_A, base)
    r = await client.get("/api/onboarding")
    assert _field(r.json(), field) == foreign, f"{fact}: another user's row lit the checklist"

    _fact(db, USER_A, fact)
    r = await client.get("/api/onboarding")
    assert _field(r.json(), field) == own, f"{fact}: the caller's own row was not read (vacuous)"


def test_floor1_onboarding_fact_cases_cover_every_fact():
    assert {c[0] for c in FACT_CASES} == set(EVERY_FACT)


@pytest.mark.asyncio
async def test_floor1_onboarding_every_statement_carries_the_caller(world):
    """Each statement ``GET`` runs binds the caller's id; the quiz branch via ``courses``."""
    client, _db, log = world
    r = await client.get("/api/onboarding")
    assert r.status_code == 200
    assert len(log) >= 5, f"fewer statements than facts: {len(log)}"
    quiz = []
    for statement in log:
        sql, params = _compiled(statement)
        assert USER_A in params.values(), f"statement without the caller: {sql}"
        assert USER_B not in params.values(), sql
        if "quiz_attempts" in tables_in(statement):
            quiz.append(sql)
    assert quiz, "the quiz_attempts branch was never queried"
    for sql in quiz:
        assert "courses.user_id = " in sql, f"quiz_attempts not scoped through courses: {sql}"


# ── PATCH ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("checklist", ["dismissed", "pinned", "auto"])
async def test_floor1_onboarding_patch_writes_only_the_callers_row(world, checklist):
    """``PATCH`` updates ``users`` keyed on ``users.id == caller``; no other row moves."""
    from sqlalchemy.sql.dml import Update

    client, db, log = world
    before = {u.id: u.onboarding_checklist for u in db.rows["users"]}
    r = await client.patch("/api/onboarding", json={"checklist": checklist})
    assert r.status_code == 200, r.text
    assert r.json()["checklist"] == checklist

    after = {u.id: u.onboarding_checklist for u in db.rows["users"]}
    assert after[USER_A] == checklist
    assert after[USER_B] == before[USER_B] == "pinned"

    updates = [s for s in log if isinstance(s, Update)]
    assert len(updates) == 1, updates
    sql, params = _compiled(updates[0])
    assert updates[0].table.name == "users"
    assert "WHERE users.id = " in sql and USER_A in params.values(), sql


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [{"checklist": "dismissed", "user_id": USER_B}, {"checklist": "dismissed", "id": USER_B}],
)
async def test_floor1_onboarding_patch_rejects_a_named_target(world, payload):
    """The body cannot name another user: unknown fields are a 422 and nothing is written."""
    client, db, log = world
    r = await client.patch("/api/onboarding", json=payload)
    assert r.status_code == 422
    assert {u.id: u.onboarding_checklist for u in db.rows["users"]} == {
        USER_A: "auto",
        USER_B: "pinned",
    }
    assert log == []

"""Floor 1 / 3 / 4 pins for the weak-spot engine's targeted generation (ADR 0007).

M33-S2-SAFETY-024 (GL#45). ``POST /api/weak-spots/targeted`` records a
``targeted_generations`` row and enqueues ``app.pipeline.targeted_task`` with the
row id only; the worker loads the row and acts as ``row.user_id`` from then on.
Two worker functions read the row without a ``user_id`` predicate and are
classified in ``UNSCOPED_FUNCTION_ALLOWED``: ``_claim`` (it has only the id) and
``_recover_stuck`` (a cross-user beat job). These tests pin what those
classifications rest on.

Pins, all over :class:`~tests.safety._minidb.MiniDB` so the answers depend on
what is in the tables, not on a mock that answers every query alike:

* the worker never inserts for another user: a row owned by A that names B's
  course generates nothing and calls no adapter; A's own row inserts only into
  A's course, dedups only against A's items, and spends as A; every statement
  on a user-owned table is filtered on A, except the one claim of the row by id;
* the task signature carries the row id only, and the two unscoped functions
  are named only inside ``targeted_task.py`` (and the Celery app);
* a row recovered (failed) while the model ran gets nothing inserted (floor 4),
  and recovery touches ``targeted_generations`` only and never deletes;
* pipeline regeneration archives only ``origin='pipeline'`` items (floor 4);
* the daily cap counts the caller's own rows since UTC midnight, and the spend
  path checks the cap only after the 404 and in-flight branches and before the
  AI quota.

The consent gate (floor 3) on the targeted route is pinned in
``test_floor3_ai_consent_gate.py``: the route is in ``KNOWN_GATED`` there, so the
derivation (it reaches ``.delay()``) cannot silently drop it.
"""

from __future__ import annotations

import ast
import inspect
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.sql.dml import Delete, Insert, Update
from sqlalchemy.sql.selectable import Select

from tests.safety._minidb import MiniDB, MiniSession, Result
from tests.safety._source import app_modules, docstring_nodes, dotted, parse, rel
from tests.safety._tenant import filters_on_user, tables_in, user_owned_tables

USER_A = "user-a-0000"
USER_B = "user-b-0000"
WEEK = 3
NOW = datetime(2026, 10, 15, 1, 0, tzinfo=UTC)


# ── world ──────────────────────────────────────────────────────────────


class _Session(MiniSession):
    """MiniSession that records statements and adds, with the calls the worker makes."""

    def __init__(self, db: MiniDB, log: list[Any]) -> None:
        super().__init__(db)
        self.log = log

    async def execute(self, statement: Any, *a: Any, **k: Any):
        self.log.append(statement)
        return await super().execute(statement, *a, **k)

    def add(self, obj: Any, *a: Any, **k: Any) -> None:
        self.log.append(("add", obj))
        super().add(obj)

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None

    def begin_nested(self):
        @asynccontextmanager
        async def _nested():
            yield self

        return _nested()


class _IdentityMapSession(_Session):
    """A session with SQLAlchemy's identity-map semantics under ``expire_on_commit=False``.

    The app's sessions (``app.core.database``) do not expire on commit. A SELECT of
    an entity the session already holds returns *that* object with its attributes as
    last loaded, even under ``FOR UPDATE``, unless the statement carries
    ``populate_existing``; a commit flushes only the attributes this session changed.
    MiniDB rows stand for the database, and the session hands out its own copies, so
    a change another session (the recovery job) makes to the database row is not
    seen through a stale copy. A plain MiniSession shares one object with the
    "database" and so cannot show the stale read (M33-S2-AI-053).
    """

    def __init__(self, db: MiniDB, log: list[Any]) -> None:
        super().__init__(db, log)
        self.identity: dict[tuple[str, Any], tuple[Any, Any, dict[str, Any]]] = {}

    @staticmethod
    def _state(obj: Any) -> dict[str, Any]:
        mapper = sa_inspect(type(obj))
        return {p.key: getattr(obj, p.key, None) for p in mapper.column_attrs}

    def _mapped(self, obj: Any, populate: bool) -> Any:
        if not hasattr(type(obj), "__table__") or not hasattr(type(obj), "__mapper__"):
            return obj
        key = (type(obj).__table__.name, sa_inspect(obj).identity or id(obj))
        if key not in self.identity:
            copy = type(obj)()
            state = self._state(obj)
            for attr, val in state.items():
                setattr(copy, attr, val)
            self.identity[key] = (copy, obj, state)
        elif populate:
            copy, _, _ = self.identity[key]
            state = self._state(obj)
            for attr, val in state.items():
                setattr(copy, attr, val)
            self.identity[key] = (copy, obj, state)
        return self.identity[key][0]

    async def execute(self, statement: Any, *a: Any, **k: Any):
        result = await super().execute(statement, *a, **k)
        if not isinstance(statement, Select):
            return result
        populate = bool(statement.get_execution_options().get("populate_existing", False))
        return Result([tuple(self._mapped(v, populate) for v in row) for row in result.all()])

    async def flush(self, *_a: Any, **_k: Any) -> None:
        for key, (copy, row, loaded) in list(self.identity.items()):
            now = self._state(copy)
            for attr, val in now.items():
                if val != loaded.get(attr):
                    setattr(row, attr, val)
            self.identity[key] = (copy, row, now)

    async def commit(self) -> None:
        await self.flush()


def _world() -> tuple[MiniDB, dict[str, Any]]:
    from app.models.artifact import LectureArtifact
    from app.models.course import Course
    from app.models.extraction import Extraction
    from app.models.quiz import QuizQuestion
    from app.models.quiz_attempt import QuizAttempt

    db = MiniDB()
    ids: dict[str, Any] = {}
    for owner, tag in ((USER_A, "a"), (USER_B, "b")):
        course, art = f"course-{tag}", f"art-{tag}"
        db.add(Course(id=course, user_id=owner, code="CSIT302", name="Course"))
        db.add(
            LectureArtifact(
                id=art,
                user_id=owner,
                course_id=course,
                week=WEEK,
                status="processed",
                original_filename=f"{tag}.pdf",
                created_at=datetime(2026, 9, 1, tzinfo=UTC),
            )
        )
        db.add(
            Extraction(
                id=f"ext-{tag}",
                artifact_id=art,
                manifest_json={"pages": [{"page_number": 1, "text": f"{tag} page one"}]},
                extraction_path=f"/x/{tag}",
            )
        )
        question = QuizQuestion(
            id=f"q-{tag}",
            course_id=course,
            week=WEEK,
            question_type="short_answer",
            question=f"{tag.upper()}-own existing stem",
            correct_answer="x",
            source_artifact_id=art,
            source_page_ref=1,
            generation_version=1,
            origin="pipeline",
            created_at=datetime(2026, 9, 2, tzinfo=UTC),
        )
        db.add(question)
        db.add(
            QuizAttempt(
                id=f"att-{tag}",
                quiz_question_id=question.id,
                is_correct=False,
                created_at=NOW - timedelta(days=1),
            )
        )
        ids[tag] = {"course": course, "artifact": art}
    return db, ids


def _generation(db: MiniDB, *, owner: str, course_id: str, status: str = "queued"):
    from app.models.targeted_generation import TargetedGeneration

    row = TargetedGeneration(
        id=f"gen-{owner}-{course_id}",
        user_id=owner,
        course_id=course_id,
        week=WEEK,
        kind="quiz",
        status=status,
        requested_count=5,
        topics=[],
        created_at=NOW,
        updated_at=NOW,
    )
    db.add(row)
    return row


def _agent(generate=None) -> MagicMock:
    from app.agents.base import QuizQuestionData

    agent = MagicMock()
    agent.generate_quiz = generate or AsyncMock(
        return_value=[
            QuizQuestionData(
                question_type="short_answer",
                question=f"Brand new targeted stem {i}",
                correct_answer="y",
                explanation="z",
                source_page_ref=1,
            )
            for i in range(3)
        ]
    )
    return agent


async def _run_task(db: MiniDB, generation_id: str, agent: MagicMock) -> dict[str, Any]:
    from app.pipeline import targeted_task

    log: list[Any] = []

    @asynccontextmanager
    async def factory():
        yield _IdentityMapSession(db, log)

    get_agent = MagicMock(return_value=agent)
    ai_context = AsyncMock(return_value=({}, "en"))
    usage = AsyncMock()
    with (
        patch.object(targeted_task, "async_session_factory", factory),
        patch.object(targeted_task, "get_agent", get_agent),
        patch.object(targeted_task, "get_user_ai_context", ai_context),
        patch.object(targeted_task, "record_agent_usage", usage),
    ):
        result = await targeted_task._run(generation_id, final=True)
    return {
        "result": result,
        "log": log,
        "get_agent": get_agent,
        "ai_context": ai_context,
        "usage": usage,
    }


def _items(db: MiniDB) -> list[Any]:
    return list(db.rows["quiz_questions"]) + list(db.rows["flashcards"])


# ── floor 1: the worker acts only as the row's owner ───────────────────


async def test_floor1_targeted_task_inserts_only_into_the_row_owners_course() -> None:
    """Control: A's row inserts only for A, dedups only against A, spends as A."""
    db, ids = _world()
    gen = _generation(db, owner=USER_A, course_id=ids["a"]["course"])
    b_before = {(o.id, o.archived_at) for o in _items(db) if o.course_id == ids["b"]["course"]}
    agent = _agent()

    out = await _run_task(db, gen.id, agent)

    assert out["result"]["status"] == "completed", out["result"]
    new = [o for o in _items(db) if o.origin == "targeted"]
    assert len(new) == 3
    assert {(o.course_id, o.source_artifact_id) for o in new} == {
        (ids["a"]["course"], ids["a"]["artifact"])
    }, "targeted items landed outside the row owner's course"
    assert {o.targeted_generation_id for o in new} == {gen.id}
    b_after = {(o.id, o.archived_at) for o in _items(db) if o.course_id == ids["b"]["course"]}
    assert b_after == b_before, "another user's items changed"

    focus = agent.generate_quiz.await_args.kwargs["focus"]
    seen = " ".join([*focus.avoid, *focus.missed_questions, *focus.topics])
    assert "B-own existing stem" not in seen, "dedup/missed read another user's items"
    assert "A-own existing stem" in focus.avoid
    assert out["ai_context"].await_args.args[1] == USER_A
    assert out["usage"].await_args.args[1] == USER_A

    owned = user_owned_tables()
    unscoped = [
        s
        for s in out["log"]
        if not isinstance(s, tuple) and tables_in(s) & owned and not filters_on_user(s, USER_A)
    ]
    # The single exception is _claim: it selects the row by id, FOR UPDATE.
    assert len(unscoped) == 1, [str(s) for s in unscoped]
    claim = unscoped[0]
    assert tables_in(claim) == {"targeted_generations"}
    assert claim._for_update_arg is not None  # noqa: SLF001
    assert not isinstance(claim, Update | Delete | Insert)


async def test_floor1_targeted_task_never_generates_into_another_users_course() -> None:
    """A row owned by A that names B's course must yield nothing at all."""
    db, ids = _world()
    gen = _generation(db, owner=USER_A, course_id=ids["b"]["course"])
    before = {(o.id, o.archived_at) for o in _items(db)}
    agent = _agent()

    out = await _run_task(db, gen.id, agent)

    assert out["result"]["status"] == "failed"
    assert gen.status == "failed" and gen.error_code == "no_source"
    assert {(o.id, o.archived_at) for o in _items(db)} == before
    out["get_agent"].assert_not_called()
    agent.generate_quiz.assert_not_called()


def test_floor1_targeted_task_takes_the_row_id_only() -> None:
    """The payload names no user: the owner can only come from the row."""
    from app.pipeline import targeted_task

    params = list(inspect.signature(targeted_task.generate_targeted_items.run).parameters)
    assert params == ["generation_id"], params
    assert list(inspect.signature(targeted_task._run).parameters) == ["generation_id", "final"]


#: The unscoped targeted-task functions classified in UNSCOPED_FUNCTION_ALLOWED,
#: and the task names that reach them.
UNSCOPED_TARGETED = {"_claim", "_recover_stuck", "recover_stuck_generations"}
TARGETED_REFERENCE_ALLOWED = {"app/pipeline/targeted_task.py", "app/worker.py"}


def test_floor1_targeted_unscoped_functions_are_worker_only() -> None:
    found: set[tuple[str, int]] = set()
    for path in app_modules():
        tree = parse(path)
        docs = docstring_nodes(tree)
        for node in ast.walk(tree):
            hit = False
            if isinstance(node, ast.ImportFrom):
                hit = any(a.name in UNSCOPED_TARGETED for a in node.names)
            elif isinstance(node, ast.Call):
                hit = dotted(node.func).split(".")[-1] in UNSCOPED_TARGETED
            elif (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docs
            ):
                hit = node.value.endswith("recover_stuck_generations")
            if hit:
                found.add((rel(path), node.lineno))
    assert found, "detector found nothing: the targeted task moved or was renamed"
    outside = sorted(f for f in found if f[0] not in TARGETED_REFERENCE_ALLOWED)
    assert not outside, f"targeted unscoped functions reached from outside the worker: {outside}"


# ── floor 4: insert-only, recovered rows stay empty ────────────────────


async def test_floor4_recovered_row_gets_no_items_inserted_later() -> None:
    """Recovery fails the row while the model runs: the late result inserts nothing.

    Runs on :class:`_IdentityMapSession`: recovery changes the *database* row while the
    worker's session still holds its own ``running`` copy from ``_claim``, which is the
    path a re-read on a shared object cannot show.
    """
    db, ids = _world()
    gen = _generation(db, owner=USER_A, course_id=ids["a"]["course"])
    before = {(o.id, o.archived_at) for o in _items(db)}
    inner = _agent().generate_quiz

    async def recovered_meanwhile(**kwargs):
        gen.status, gen.error_code = "failed", "timeout"
        return await inner(**kwargs)

    out = await _run_task(db, gen.id, _agent(AsyncMock(side_effect=recovered_meanwhile)))

    assert out["result"]["status"] == "failed"
    assert {(o.id, o.archived_at) for o in _items(db)} == before, "items inserted on a dead row"
    assert gen.status == "failed" and gen.error_code == "timeout", "recovery's verdict overwritten"


async def test_floor4_stuck_generation_recovery_only_fails_rows() -> None:
    from app.pipeline import targeted_task

    log: list[Any] = []
    session = MagicMock()

    async def execute(statement, *_a, **_k):
        log.append(statement)
        result = MagicMock()
        result.scalars.return_value.all.return_value = ["gen-1"]
        return result

    session.execute = execute
    session.commit = AsyncMock()

    @asynccontextmanager
    async def factory():
        yield session

    with patch.object(targeted_task, "async_session_factory", factory):
        ids = await targeted_task._recover_stuck(now=NOW)

    assert ids == ["gen-1"]
    assert len(log) == 1
    stmt = log[0]
    assert isinstance(stmt, Update) and tables_in(stmt) == {"targeted_generations"}
    values = {getattr(c, "key", str(c)): v.value for c, v in stmt._values.items()}  # noqa: SLF001
    assert values["status"] == "failed" and values["error_code"] == "timeout"
    assert set(values) == {"status", "error_code", "completed_at"}
    tree = parse(next(p for p in app_modules() if rel(p) == "app/pipeline/targeted_task.py"))
    fn = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "_recover_stuck"
    )
    calls = {dotted(c.func).split(".")[-1] for c in ast.walk(fn) if isinstance(c, ast.Call)}
    assert not calls & {"delete", "remove", "unlink", "rmtree", "sa_delete"}


async def test_floor4_regeneration_never_archives_targeted_items() -> None:
    from app.models.flashcard import Flashcard
    from app.models.quiz import QuizQuestion
    from app.services import asset_service

    db = MiniDB()
    common = {"course_id": "course-a", "week": WEEK, "source_artifact_id": "art-a"}
    for origin in ("pipeline", "targeted"):
        db.add(
            Flashcard(
                id=f"fc-{origin}",
                front="f",
                back="b",
                origin=origin,
                generation_version=1,
                **common,
            )
        )
        db.add(
            QuizQuestion(
                id=f"q-{origin}",
                question_type="short_answer",
                question="q",
                correct_answer="a",
                origin=origin,
                generation_version=1,
                **common,
            )
        )

    class _VersionAware(_Session):
        async def execute(self, statement, *a, **k):
            # MiniDB models count() only; the max(version) read is not under test.
            if "max(" in str(statement):
                self.log.append(statement)
                result = MagicMock()
                result.scalar.return_value = 1
                return result
            return await super().execute(statement, *a, **k)

    session = _VersionAware(db, [])
    await asset_service.save_flashcards(session, "course-a", WEEK, "art-a", [])
    await asset_service.save_quiz_questions(session, "course-a", WEEK, "art-a", [])

    by_id = {o.id: o for o in _items(db)}
    assert set(by_id) == {"fc-pipeline", "fc-targeted", "q-pipeline", "q-targeted"}
    assert by_id["fc-targeted"].archived_at is None, "regeneration archived targeted practice"
    assert by_id["q-targeted"].archived_at is None, "regeneration archived targeted practice"
    assert by_id["fc-pipeline"].archived_at is not None  # control: the harness archives
    assert by_id["q-pipeline"].archived_at is not None


# ── floor 1 / 3: daily cap per user per UTC day; spend-path order ──────


async def _request(db: MiniDB, *, owner: str, course_id: str) -> tuple[Any, AsyncMock]:
    from app.services import weakspot_service

    quota = AsyncMock()
    with (
        patch.object(weakspot_service, "utc_now", return_value=NOW),
        patch.object(weakspot_service.quota_service, "check_ai_quota", quota),
    ):
        try:
            out = await weakspot_service.request_targeted_generation(
                _Session(db, []),
                user_id=owner,
                user_tier="free",
                course_id=course_id,
                week=WEEK,
                kind="quiz",
            )
        except Exception as exc:  # noqa: BLE001  (the verdict is the exception)
            out = exc
    return out, quota


def _past(db: MiniDB, *, owner: str, course_id: str, at: datetime, n: int, tag: str) -> None:
    from app.models.targeted_generation import TargetedGeneration

    for i in range(n):
        db.add(
            TargetedGeneration(
                id=f"old-{tag}-{i}",
                user_id=owner,
                course_id=course_id,
                week=WEEK + 1 + i,
                kind="quiz",
                status="completed",
                requested_count=5,
                topics=[],
                created_at=at,
            )
        )


async def test_floor1_daily_cap_counts_the_callers_rows_in_the_utc_day() -> None:
    from app.core.exceptions import TargetedDailyCapError
    from app.services.weakspot_service import TARGETED_GENERATIONS_PER_DAY as CAP

    midnight = datetime(2026, 10, 15, tzinfo=UTC)

    # Capped: CAP of A's own rows since UTC midnight (one exactly at midnight).
    db, ids = _world()
    _past(db, owner=USER_A, course_id=ids["a"]["course"], at=NOW, n=CAP - 1, tag="t")
    _past(db, owner=USER_A, course_id=ids["a"]["course"], at=midnight, n=1, tag="m")
    out, quota = await _request(db, owner=USER_A, course_id=ids["a"]["course"])
    assert isinstance(out, TargetedDailyCapError), out
    quota.assert_not_called()
    assert len(db.rows["targeted_generations"]) == CAP

    # Another user's rows today never count against the caller.
    db, ids = _world()
    _past(db, owner=USER_B, course_id=ids["b"]["course"], at=NOW, n=CAP, tag="b")
    out, quota = await _request(db, owner=USER_A, course_id=ids["a"]["course"])
    assert isinstance(out, tuple) and out[1] is True, out
    assert out[0].user_id == USER_A
    assert quota.await_args.args[1] == USER_A

    # Yesterday (UTC) is spent, even if it was under 24 hours ago.
    db, ids = _world()
    _past(
        db,
        owner=USER_A,
        course_id=ids["a"]["course"],
        at=midnight - timedelta(minutes=30),
        n=CAP,
        tag="y",
    )
    out, _ = await _request(db, owner=USER_A, course_id=ids["a"]["course"])
    assert isinstance(out, tuple) and out[1] is True, out


async def test_floor3_targeted_spend_path_order() -> None:
    """404 before cap, in-flight before cap, cap before quota, quota before insert."""
    from app.core.exceptions import QuotaExceededError, TargetedUnitNotFoundError
    from app.services import weakspot_service
    from app.services.weakspot_service import TARGETED_GENERATIONS_PER_DAY as CAP

    # A foreign course is a 404 even for a capped caller, and spends nothing.
    db, ids = _world()
    _past(db, owner=USER_A, course_id=ids["a"]["course"], at=NOW, n=CAP, tag="t")
    out, quota = await _request(db, owner=USER_A, course_id=ids["b"]["course"])
    assert isinstance(out, TargetedUnitNotFoundError), out
    quota.assert_not_called()

    # An in-flight job is returned (no new row) even when the cap is reached.
    db, ids = _world()
    _past(db, owner=USER_A, course_id=ids["a"]["course"], at=NOW, n=CAP, tag="t")
    flight = _generation(db, owner=USER_A, course_id=ids["a"]["course"], status="running")
    out, quota = await _request(db, owner=USER_A, course_id=ids["a"]["course"])
    assert isinstance(out, tuple) and out == (flight, False), out
    quota.assert_not_called()

    # Another user's in-flight row is never the caller's, even naming the caller's course.
    db, ids = _world()
    _generation(db, owner=USER_B, course_id=ids["a"]["course"], status="running")
    out, _ = await _request(db, owner=USER_A, course_id=ids["a"]["course"])
    assert isinstance(out, tuple) and out[1] is True and out[0].user_id == USER_A

    # The quota refuses before any row is written.
    db, ids = _world()
    with (
        patch.object(weakspot_service, "utc_now", return_value=NOW),
        patch.object(
            weakspot_service.quota_service,
            "check_ai_quota",
            AsyncMock(side_effect=QuotaExceededError("ai_calls", 1, "day")),
        ),
        pytest.raises(QuotaExceededError),
    ):
        await weakspot_service.request_targeted_generation(
            _Session(db, []),
            user_id=USER_A,
            user_tier="free",
            course_id=ids["a"]["course"],
            week=WEEK,
            kind="quiz",
        )
    assert db.rows["targeted_generations"] == []

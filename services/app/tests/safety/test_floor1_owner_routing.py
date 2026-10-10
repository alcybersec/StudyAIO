"""Floor 1 — owner routing for pipeline SSE events and chat course scoping.

Two request-adjacent paths that pick *whose* data a user sees without going
through a route the sweep can drive:

* Pipeline SSE events (R-022, AI-021). A stage acts as ``artifact.user_id``;
  the Celery payload's ``user_id`` is advisory. An event published to the
  payload user's channel for a row someone else owns tells that user another
  user's artifact id and pipeline progress. The payload user must never
  receive an event for a row it does not own, and an unknown owner drops the
  event rather than guessing.
* Chat course scoping (GL#10, BACKEND-019). A course code typed into a chat
  message is resolved against the caller's courses. A code another user owns
  must be indistinguishable from one nobody owns, or chat is an existence
  oracle for other users' course codes. Sources are derived from the
  caller-scoped chunk list only, never from the adapter's own citation list.
"""

from __future__ import annotations

import ast
import contextlib
import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.safety._source import app_modules, dotted, parse, rel
from tests.safety._tenant import filters_on_user, tables_in

ROW_OWNER = "user-row-owner"
PAYLOAD_USER = "user-payload-other"
ART = "art-floor1"

PUBLISHERS = ("publish_pipeline_event_sync", "publish_pipeline_event")

# (module, task attr, non-retry error class name)
STAGES = [
    ("classify", "classify_artifact", "ClassificationError"),
    ("extract", "extract_artifact", "ExtractionError"),
    ("summarize", "summarize_artifact", "SummarizationError"),
    ("index", "index_artifact", "IndexingError"),
    ("assets", "generate_assets", "AssetGenerationError"),
]


# ── SSE events: structural ─────────────────────────────────────────────


def _publish_calls(tree: ast.AST):
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.Call) and dotted(node.func).split(".")[-1] in PUBLISHERS:
                yield fn, node


def _assigned_values(fn: ast.AST, name: str) -> list[ast.AST]:
    values = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign | ast.AugAssign | ast.NamedExpr):
            targets = [node.target]
        else:
            continue
        if any(isinstance(t, ast.Name) and t.id == name for t in targets):
            values.append(node.value)
    return values


def _calls_resolver(value: ast.AST | None) -> bool:
    return value is not None and any(
        isinstance(n, ast.Call) and dotted(n.func).split(".")[-1] == "resolve_event_owner"
        for n in ast.walk(value)
    )


def _kwonly_params(fn: ast.AST) -> set[str]:
    return {a.arg for a in fn.args.kwonlyargs}


def test_floor1_pipeline_events_publish_to_a_resolved_owner():
    """Every pipeline publish names an owner that went through resolve_event_owner.

    The recipient must be a local whose every assignment calls
    ``resolve_event_owner`` (the row-owner lookup), or a keyword-only parameter
    of a relay helper whose every call site passes such a local (SAFETY-027:
    ``resilience.handle_retryable``). Handing the publisher the
    payload ``user_id`` directly — the R-022 bug — fails here, as does a new
    stage that never resolves. Publishing is confined to ``app/pipeline/`` and
    the publisher module itself.
    """
    bad, seen, outside = [], 0, []
    trees = {rel(path): parse(path) for path in app_modules()}
    relays: dict[str, str] = {}  # relay function name -> its recipient parameter
    for module, tree in trees.items():
        for fn, call in _publish_calls(tree):
            if module == "app/services/event_service.py":
                continue  # the publisher and its sync wrapper
            if not module.startswith("app/pipeline/"):
                outside.append(f"{module}::{fn.name} line {call.lineno}")
                continue
            seen += 1
            kw = next((k.value for k in call.keywords if k.arg == "user_id"), None)
            if isinstance(kw, ast.Name) and kw.id in _kwonly_params(fn):
                # A relay (TECH-04 ``handle_retryable``): the recipient is the
                # caller's to resolve, so every call site is checked below.
                if _assigned_values(fn, kw.id):
                    bad.append(f"{module}::{fn.name} line {call.lineno} (relay reassigns)")
                relays[fn.name] = kw.id
                continue
            values = _assigned_values(fn, kw.id) if isinstance(kw, ast.Name) else []
            if not values or not all(_calls_resolver(v) for v in values):
                bad.append(f"{module}::{fn.name} line {call.lineno}")
    relay_calls = 0
    for module, tree in trees.items():
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for call in ast.walk(fn):
                if not isinstance(call, ast.Call):
                    continue
                name = dotted(call.func).split(".")[-1]
                if name not in relays or fn.name == name:
                    continue
                relay_calls += 1
                where = f"{module}::{fn.name} line {call.lineno} -> {name}"
                if not module.startswith("app/pipeline/"):
                    outside.append(where)
                    continue
                kw = next((k.value for k in call.keywords if k.arg == relays[name]), None)
                values = _assigned_values(fn, kw.id) if isinstance(kw, ast.Name) else []
                if not values or not all(_calls_resolver(v) for v in values):
                    bad.append(where)
    assert seen >= 20, f"detector went blind: saw only {seen} pipeline publish calls"
    assert not relays or relay_calls, f"relay(s) {sorted(relays)} found but no call site seen"
    assert not outside, f"pipeline events published outside the worker: {outside}"
    assert not bad, (
        "Floor 1: pipeline event published to an owner that was not resolved from the "
        "artifact row, so the payload user can receive another owner's event (R-022):\n  "
        + "\n  ".join(bad)
    )


# ── SSE events: behaviour ──────────────────────────────────────────────


def _effect(effect):
    if isinstance(effect, BaseException):
        return {"side_effect": effect}
    return {"return_value": effect}


def _recipients(pub: MagicMock) -> list:
    return [c.kwargs.get("user_id") for c in pub.call_args_list]


def _run_stage(mod_name, task_name, effect, row_owner):
    mod = importlib.import_module(f"app.pipeline.{mod_name}")
    with (
        patch(f"app.pipeline.{mod_name}.publish_pipeline_event_sync") as pub,
        patch(f"app.pipeline.{mod_name}.run_async", **_effect(effect)),
        patch("app.pipeline._owner._row_owner", return_value=row_owner),
        contextlib.suppress(BaseException),
    ):
        getattr(mod, task_name)({"artifact_id": ART, "user_id": PAYLOAD_USER})
    return pub


def _outcomes(mod_name, err_name):
    err = getattr(importlib.import_module(f"app.pipeline.{mod_name}"), err_name)
    return [
        {"artifact_id": ART, "status": "completed"},
        {"artifact_id": ART, "status": "waiting_review"},
        err("boom"),
        RuntimeError("transient"),
    ]


@pytest.mark.parametrize(("mod", "task", "err"), STAGES)
def test_floor1_payload_user_never_receives_another_owners_stage_event(mod, task, err):
    """Row owned by A, payload names B: B's channel gets nothing, on every outcome."""
    for outcome in _outcomes(mod, err):
        pub = _run_stage(mod, task, outcome, row_owner=ROW_OWNER)
        got = _recipients(pub)
        assert got, f"control: {mod} published nothing for {outcome!r}"
        assert PAYLOAD_USER not in got, (
            f"Floor 1 VIOLATION: {mod} published to the payload user for a row owned by "
            f"another user ({outcome!r}): {got}"
        )
        assert set(got) == {ROW_OWNER}


@pytest.mark.parametrize(("mod", "task", "err"), STAGES)
def test_floor1_unknown_row_owner_drops_stage_events(mod, task, err):
    """No row (or a failed lookup): every publish names no owner, so it is dropped."""
    for outcome in _outcomes(mod, err):
        pub = _run_stage(mod, task, outcome, row_owner=None)
        assert all(o is None for o in _recipients(pub)), (
            f"Floor 1 VIOLATION: {mod} guessed an owner for an unknown row: {_recipients(pub)}"
        )


def _run_ingest(payload, effect, row_owner):
    from app.pipeline.ingest import ingest_file

    with (
        patch("app.pipeline.ingest.publish_pipeline_event_sync") as pub,
        patch("app.pipeline.ingest.run_async", **_effect(effect)),
        patch("app.pipeline._owner._row_owner", return_value=row_owner),
        contextlib.suppress(BaseException),
    ):
        ingest_file(payload)
    return pub


@pytest.mark.parametrize(
    "effect",
    [
        {"artifact_id": ART, "status": "ingested"},
        {"artifact_id": "earlier-row", "status": "duplicate"},
        RuntimeError("transient"),
    ],
)
def test_floor1_ingest_with_precreated_row_never_reaches_payload_user(effect):
    """Uploads pass the artifact id; a row owned by A never notifies payload user B."""
    payload = {"file_path": "f.pdf", "user_id": PAYLOAD_USER, "artifact_id": ART}
    got = _recipients(_run_ingest(payload, effect, row_owner=ROW_OWNER))
    assert got and PAYLOAD_USER not in got, f"Floor 1 VIOLATION: ingest recipients {got}"
    got = _recipients(_run_ingest(payload, effect, row_owner=None))
    assert all(o is None for o in got), f"Floor 1 VIOLATION: ingest guessed an owner: {got}"


def test_floor1_ingest_without_row_uses_payload_user_only_before_the_row_exists():
    """Pre-row ingest: the placeholder events go to the payload user, who becomes the owner.

    Once the run names a row, the result event is re-resolved from that row, so
    a result naming a row someone else owns still never reaches the payload user.
    """
    created = {"artifact_id": "new-row", "status": "ingested"}
    pub = _run_ingest({"file_path": "f.pdf", "user_id": PAYLOAD_USER}, created, ROW_OWNER)
    assert [c.args[0] for c in pub.call_args_list] == ["pending", "new-row"]
    assert _recipients(pub) == [PAYLOAD_USER, ROW_OWNER]

    failed = _run_ingest({"file_path": "f.pdf", "user_id": PAYLOAD_USER}, RuntimeError(), None)
    assert [c.args[0] for c in failed.call_args_list] == ["pending", "unknown"]
    assert _recipients(failed) == [PAYLOAD_USER, PAYLOAD_USER]


def test_floor1_event_owner_lookup_fails_closed():
    """resolve_event_owner: row wins over payload; a miss or an error returns None."""
    from app.pipeline import _owner

    with patch.object(_owner, "_row_owner", return_value=ROW_OWNER):
        assert _owner.resolve_event_owner("x", ART, PAYLOAD_USER) == ROW_OWNER
    with patch.object(_owner, "_row_owner", return_value=None):
        assert _owner.resolve_event_owner("x", ART, PAYLOAD_USER) is None
    with patch.object(_owner, "_row_owner", side_effect=RuntimeError("db down")):
        assert _owner.resolve_event_owner("x", ART, PAYLOAD_USER) is None


@pytest.mark.asyncio
async def test_floor1_publisher_drops_an_ownerless_event():
    """A ``None`` owner publishes to no channel at all."""
    from app.services import event_service

    with patch.object(event_service, "Redis") as redis_cls:
        await event_service.publish_pipeline_event(ART, "classify", "started", user_id=None)
    redis_cls.from_url.assert_not_called()


def test_floor1_row_owner_lookup_is_worker_only():
    """The unscoped owner lookup is reachable only from ``app/pipeline/``."""
    callers = set()
    for path in app_modules():
        for node in ast.walk(parse(path)):
            if isinstance(node, ast.Call) and dotted(node.func).split(".")[-1] in {
                "_row_owner",
                "_row_owner_async",
                "resolve_event_owner",
            }:
                callers.add(rel(path))
    assert callers, "detector found no caller at all — it has gone blind"
    outside = sorted(c for c in callers if not c.startswith("app/pipeline/"))
    assert not outside, f"row-owner lookup called outside the worker: {outside}"


# ── chat: course code in a message ─────────────────────────────────────

OWNER_A, CALLER_B = "user-a", "user-b"


def _database_with(course_owner: str | None, caller: str):
    """A session answering like a DB holding course CSIT302 owned by ``course_owner``.

    Only a ``courses`` lookup filtered on a caller who is not the owner comes
    back empty; an unscoped one (or one on the wrong user) finds the row, so a
    dropped ``user_id`` filter does not pass on an empty mock by accident.
    """
    from app.models.course import Course

    course = MagicMock(spec=Course)
    course.id = "course-of-a"
    course.code = "CSIT302"
    course.user_id = course_owner
    statements = []

    def execute(statement, *_a, **_k):
        statements.append(statement)
        hit = (
            course_owner is not None
            and "courses" in tables_in(statement)
            and not (caller != course_owner and filters_on_user(statement, caller))
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = course if hit else None
        result.scalars.return_value.first.return_value = course if hit else None
        result.first.return_value = course if hit else None
        return result

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=execute)
    session.get = AsyncMock(return_value=course)
    return session, statements


def _plan_fields(plan) -> tuple:
    return (plan.course_id, plan.week, plan.code, plan.from_message, plan.reply, plan.action)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message",
    ["summarise CSIT302 week 3", "make a quiz on CSIT302 lecture 3", "what is in CSIT302?"],
)
async def test_floor1_chat_unowned_course_code_is_indistinguishable_from_missing(message):
    """A code owned by A looks to caller B exactly like a code nobody owns.

    Same plan (reply text, action, scope), same number of statements, so no
    branch downstream can differ either. Control: owner A resolves the course.
    """
    from app.services.chat_service import _plan_message

    owned, _ = _database_with(OWNER_A, OWNER_A)
    control = await _plan_message(owned, OWNER_A, message, None, None, None)
    assert control.course_id == "course-of-a", "control: the owner's lookup found nothing"

    foreign_db, foreign_stmts = _database_with(OWNER_A, CALLER_B)
    foreign = await _plan_message(foreign_db, CALLER_B, message, None, None, None)
    missing_db, missing_stmts = _database_with(None, CALLER_B)
    missing = await _plan_message(missing_db, CALLER_B, message, None, None, None)

    assert _plan_fields(foreign) == _plan_fields(missing), (
        "Floor 1 VIOLATION: chat answers differently for a course code another user "
        f"owns than for one nobody owns.\n  foreign: {_plan_fields(foreign)}\n"
        f"  missing: {_plan_fields(missing)}"
    )
    assert foreign.course_id is None and foreign.reply is not None
    assert "course-of-a" not in repr(_plan_fields(foreign))
    assert len(foreign_stmts) == len(missing_stmts)
    assert foreign_db.get.await_count == 0, "session.get on Course bypasses the owner filter"


@pytest.mark.asyncio
async def test_floor1_chat_sources_come_only_from_caller_scoped_chunks():
    """Stored sources name only chunks search_chunks returned for the caller.

    The adapter's own citation list (model output, injectable through lecture
    text) is ignored; an ``[n]`` past the chunk list maps to nothing.
    """
    from app.agents.base import AnswerResult
    from app.models.chat_session import ChatSession
    from app.services import chat_service

    chunks = [
        {"chunk_id": f"own-{i}", "text": "t", "artifact_id": "own-art", "course_code": "X"}
        for i in (1, 2)
    ]
    chat = MagicMock(spec=ChatSession)
    chat.id, chat.user_id, chat.course_id = "s1", CALLER_B, None
    chat.title, chat.message_count = "New Chat", 0
    own = MagicMock()
    own.scalar_one_or_none.return_value = chat
    hist = MagicMock()
    hist.scalars.return_value.all.return_value = []
    session = AsyncMock()
    session.add = MagicMock()
    session.execute = AsyncMock(side_effect=[own, hist])

    agent = AsyncMock()
    agent.answer_question.return_value = AnswerResult(
        answer="see [1] and [2] and [9]",
        citations=[{"chunk_id": "victim-chunk", "artifact_id": "victim-art"}],
    )
    provider = MagicMock()
    provider.embed_texts.return_value = [[0.1]]
    search = AsyncMock(return_value=chunks)
    with (
        patch.object(chat_service, "get_embedding_provider", return_value=provider),
        patch.object(chat_service.search_service, "search_chunks", search),
        patch.object(chat_service, "get_agent", return_value=agent),
        patch(
            "app.services.settings_service.get_user_ai_context",
            new_callable=AsyncMock,
            return_value=(None, None),
        ),
    ):
        await chat_service.send_message(session, "s1", CALLER_B, "explain this")

    assert search.await_args.kwargs["user_id"] == CALLER_B
    stored = [c.args[0] for c in session.add.call_args_list]
    reply = next(m for m in stored if getattr(m, "role", None) == "assistant")
    ids = {s.get("chunk_id") for s in reply.citations_json or []}
    arts = {s.get("artifact_id") for s in reply.citations_json or []}
    assert ids == {"own-1", "own-2"}, f"Floor 1 VIOLATION: sources outside the chunk list: {ids}"
    assert arts == {"own-art"}


# ── chat: scope carried across turns (GL#31, backend 423b178) ────────────


def _database_with_week(course_owner: str | None, caller: str):
    """``_database_with`` plus the course-has-week listing: CSIT302 (A's) has a week 3.

    A listing not filtered on a non-owner caller returns A's code, so an
    unscoped ``_courses_with_week`` would disclose it in the clarifying reply.
    """
    session, statements = _database_with(course_owner, caller)
    inner = session.execute.side_effect

    def execute(statement, *a, **k):
        result = inner(statement, *a, **k)
        hit = (
            course_owner is not None
            and "courses" in tables_in(statement)
            and not (caller != course_owner and filters_on_user(statement, caller))
        )
        result.all.return_value = [("CSIT302",)] if hit else []
        return result

    session.execute = AsyncMock(side_effect=execute)
    return session, statements


CARRY_CASES = [
    # (earlier user messages, newest first; follow-up message)
    (["what is in CSIT302 week 2?"], "and week 3?"),
    (["explain CSIT302"], "make a quiz on that"),
    (["hello", "summarise CSIT302 week 1"], "what about the next part?"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("history", "message"), CARRY_CASES)
async def test_floor1_chat_carried_foreign_course_is_indistinguishable_from_missing(
    history, message
):
    """A code another user owns, named in an earlier turn, carries nothing and leaks nothing.

    Same plan and statement count as a code nobody owns; the owner (control)
    does carry it.
    """
    from app.services.chat_service import _plan_message

    owned, _ = _database_with_week(OWNER_A, OWNER_A)
    control = await _plan_message(owned, OWNER_A, message, None, None, None, history)
    assert control.course_id == "course-of-a", "control: the owner's carried scope was lost"

    foreign_db, foreign_stmts = _database_with_week(OWNER_A, CALLER_B)
    foreign = await _plan_message(foreign_db, CALLER_B, message, None, None, None, history)
    missing_db, missing_stmts = _database_with_week(None, CALLER_B)
    missing = await _plan_message(missing_db, CALLER_B, message, None, None, None, history)

    assert _plan_fields(foreign) == _plan_fields(missing), (
        "Floor 1 VIOLATION: a carried course code another user owns changes the chat plan.\n"
        f"  foreign: {_plan_fields(foreign)}\n  missing: {_plan_fields(missing)}"
    )
    assert foreign.course_id is None
    assert "course-of-a" not in repr(_plan_fields(foreign))
    assert len(foreign_stmts) == len(missing_stmts)
    assert foreign_db.get.await_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("message", ["what was week 3 about?", "summarise week 3"])
async def test_floor1_chat_bare_week_lists_only_the_callers_courses(message):
    """ "Which course for Week N" never names, or resolves to, another user's course.

    The DB holds A's CSIT302 with a week 3; caller B must get the same plan as
    with nothing in the DB. Control: owner A is scoped to it or offered it.
    """
    from app.services.chat_service import _plan_message

    owned, _ = _database_with_week(OWNER_A, OWNER_A)
    control = await _plan_message(owned, OWNER_A, message, None, None, None, [])
    assert control.course_id == "course-of-a" or "CSIT302" in (control.reply or ""), (
        "control: the owner's week-3 course was not found, so this proves nothing"
    )

    foreign_db, foreign_stmts = _database_with_week(OWNER_A, CALLER_B)
    foreign = await _plan_message(foreign_db, CALLER_B, message, None, None, None, [])
    missing_db, missing_stmts = _database_with_week(None, CALLER_B)
    missing = await _plan_message(missing_db, CALLER_B, message, None, None, None, [])

    assert "CSIT302" not in repr(_plan_fields(foreign)), (
        f"Floor 1 VIOLATION: chat discloses another user's course code: {_plan_fields(foreign)}"
    )
    assert _plan_fields(foreign) == _plan_fields(missing)
    assert len(foreign_stmts) == len(missing_stmts)


def test_floor1_chat_scope_carry_adds_no_ai_call_site():
    """The carried-scope helpers run no adapter: the clarifying reply is a template."""
    import inspect

    from app.services import chat_service

    for fn in (
        chat_service._carry_scope,
        chat_service._courses_with_week,
        chat_service._plan_message,
    ):
        src = inspect.getsource(fn)
        assert "get_agent" not in src and "agent." not in src, f"{fn.__name__} calls the adapter"

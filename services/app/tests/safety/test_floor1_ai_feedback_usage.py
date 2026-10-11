"""Floor 1 for AI feedback votes and usage events (GL#36, GL#37).

M33-S1-SAFETY-033 over backend ``61694a6``. Pins:

* a vote lands only on a target the caller owns, for every target type; a
  foreign target and a missing one answer the same 404 body, so the endpoint
  is no existence oracle across types, and nothing is written for either;
* ``GET /feedback/mine`` and ``DELETE /feedback/...`` touch only the caller's
  own votes, even when another user's vote sits on the same target id;
* ``POST /usage-events`` refuses a course the caller does not own, and every
  ``usage_service.record`` call in ``app/`` passes the handler's own caller id;
* the two cross-user aggregates (``admin_summary``, ``retention_readout``) are
  reachable only from their admin routes, those routes depend on
  ``require_role('admin')``, and neither result carries a user identifier.

The behavioural pins run the real routes and services over
:class:`tests.safety._minidb.MiniDB`, so a dropped ``user_id`` predicate
changes the answer rather than being masked by a mock that answers None.
"""

from __future__ import annotations

import ast
import inspect
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy.sql.elements import ColumnClause, Label
from sqlalchemy.sql.functions import FunctionElement

from tests.safety._minidb import MiniDB, MiniSession
from tests.safety._source import APP_ROOT, dotted, parse, rel

USER_A = "floor1-feedback-user-a"
USER_B = "floor1-feedback-user-b"
MISSING = "floor1-feedback-missing-id"
IDENTIFYING = frozenset({"user_id", "email", "username", "hashed_password"})


# ── MiniDB harness ─────────────────────────────────────────────────────


class _Nested:
    async def __aenter__(self) -> _Nested:
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False


class _Session(MiniSession):
    """MiniSession plus the transaction calls the feedback/usage routes make."""

    def begin_nested(self) -> _Nested:
        return _Nested()

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None

    async def refresh(self, *_a: Any, **_k: Any) -> None:
        return None


def _seed(db: MiniDB, owner: str) -> dict[str, str]:
    """One course and one target of every type for ``owner``; returns type -> id."""
    from app.models.chat_message import ChatMessage
    from app.models.chat_session import ChatSession
    from app.models.course import Course
    from app.models.flashcard import Flashcard
    from app.models.quiz import QuizQuestion
    from app.models.summary import Summary

    tag = owner.rsplit("-", 1)[-1]
    course = Course(id=f"course-{tag}", user_id=owner, code=f"C{tag}", name="c")
    chat = ChatSession(id=f"chat-{tag}", user_id=owner, course_id=course.id)
    answer = ChatMessage(id=f"answer-{tag}", session_id=chat.id, role="assistant", content="a")
    message = ChatMessage(id=f"message-{tag}", session_id=chat.id, role="user", content="q")
    summary = Summary(id=f"summary-{tag}", course_id=course.id, week=1, content_md="s")
    card = Flashcard(id=f"card-{tag}", course_id=course.id, front="f", back="b")
    question = QuizQuestion(id=f"quiz-{tag}", course_id=course.id, question="q")
    for obj in (course, chat, answer, message, summary, card, question):
        db.add(obj)
    return {
        "course": course.id,
        "summary": summary.id,
        "answer": answer.id,
        "chat_message": message.id,
        "flashcard": card.id,
        "quiz_question": question.id,
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


def _rows(db: MiniDB, table: str) -> list[Any]:
    return list(db.rows[table])


def test_floor1_every_feedback_target_type_is_seeded():
    """A new target type must be added here before its ownership check is trusted."""
    from app.services.ai_feedback_service import TARGET_TYPES

    seeded = set(_seed(MiniDB(), USER_A)) - {"course"}
    assert seeded == set(TARGET_TYPES)


# ── votes ──────────────────────────────────────────────────────────────

TARGET_TYPES = ("summary", "answer", "chat_message", "flashcard", "quiz_question")


@pytest.mark.asyncio
@pytest.mark.parametrize("target_type", TARGET_TYPES)
async def test_floor1_vote_on_foreign_target_is_a_404_identical_to_missing(world, target_type):
    client, db, ids = world
    foreign = await client.put(
        "/api/feedback",
        json={"target_type": target_type, "target_id": ids[USER_B][target_type], "rating": -1},
    )
    missing = await client.put(
        "/api/feedback", json={"target_type": target_type, "target_id": MISSING, "rating": -1}
    )
    assert foreign.status_code == 404, foreign.text
    assert (foreign.status_code, foreign.json()) == (missing.status_code, missing.json())
    assert _rows(db, "ai_feedback") == []
    assert _rows(db, "usage_events") == []


@pytest.mark.asyncio
@pytest.mark.parametrize("target_type", TARGET_TYPES)
async def test_floor1_vote_on_own_target_is_stored_for_the_caller(world, target_type):
    client, db, ids = world
    resp = await client.put(
        "/api/feedback",
        json={
            "target_type": target_type,
            "target_id": ids[USER_A][target_type],
            "rating": 1,
            "comment": "private note",
        },
    )
    assert resp.status_code == 200, resp.text
    votes = _rows(db, "ai_feedback")
    assert [(v.user_id, v.target_id) for v in votes] == [(USER_A, ids[USER_A][target_type])]
    assert votes[0].course_id == ids[USER_A]["course"]
    events = _rows(db, "usage_events")
    assert [(e.user_id, e.event) for e in events] == [(USER_A, "feedback_given")]


@pytest.mark.asyncio
async def test_floor1_list_mine_returns_only_the_callers_votes(world):
    from app.models.ai_feedback import AIFeedback

    client, db, ids = world
    shared = ids[USER_A]["summary"]
    db.add(AIFeedback(id="v-a", user_id=USER_A, target_type="summary", target_id=shared, rating=1))
    # A row of B's on the same target id (and one on B's own target).
    db.add(
        AIFeedback(id="v-b1", user_id=USER_B, target_type="summary", target_id=shared, rating=-1)
    )
    db.add(
        AIFeedback(
            id="v-b2",
            user_id=USER_B,
            target_type="summary",
            target_id=ids[USER_B]["summary"],
            rating=-1,
            comment="b's private comment",
        )
    )
    resp = await client.get(
        "/api/feedback/mine",
        params={"target_type": "summary", "target_ids": [shared, ids[USER_B]["summary"]]},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert [(i["target_id"], i["rating"]) for i in items] == [(shared, 1)]
    assert "b's private comment" not in resp.text


@pytest.mark.asyncio
async def test_floor1_delete_never_removes_another_users_vote(world):
    from app.models.ai_feedback import AIFeedback

    client, db, ids = world
    target = ids[USER_B]["flashcard"]
    db.add(
        AIFeedback(id="v-b", user_id=USER_B, target_type="flashcard", target_id=target, rating=1)
    )
    resp = await client.delete(f"/api/feedback/flashcard/{target}")
    assert resp.status_code == 404
    assert [v.id for v in _rows(db, "ai_feedback")] == ["v-b"]


# ── usage events ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_floor1_usage_event_rejects_a_foreign_course(world):
    client, db, ids = world
    resp = await client.post(
        "/api/usage-events", json={"event": "summary_viewed", "course_id": ids[USER_B]["course"]}
    )
    assert resp.status_code == 404
    assert _rows(db, "usage_events") == []


@pytest.mark.asyncio
@pytest.mark.parametrize("with_course", [True, False])
async def test_floor1_usage_event_is_recorded_for_the_caller(world, with_course):
    client, db, ids = world
    body: dict[str, Any] = {"event": "study_plan_viewed"}
    if with_course:
        body["course_id"] = ids[USER_A]["course"]
    resp = await client.post("/api/usage-events", json=body)
    assert resp.status_code == 204, resp.text
    events = _rows(db, "usage_events")
    assert [(e.user_id, e.course_id) for e in events] == [
        (USER_A, ids[USER_A]["course"] if with_course else None)
    ]


CALLER_DEPENDENCIES = frozenset({"get_current_user", "get_current_user_or_default"})


def _caller_param(fn: ast.AST) -> str | None:
    args = fn.args
    defaults = (
        dict(zip([a.arg for a in args.args][-len(args.defaults) :], args.defaults, strict=False))
        if args.defaults
        else {}
    )
    defaults |= {a.arg: d for a, d in zip(args.kwonlyargs, args.kw_defaults, strict=False) if d}
    for name, default in defaults.items():
        if (
            isinstance(default, ast.Call)
            and dotted(default.func) == "Depends"
            and default.args
            and dotted(default.args[0]) in CALLER_DEPENDENCIES
        ):
            return name
    return None


def usage_record_problems(tree: ast.Module, module: str) -> list[str]:
    """Each ``usage_service.record`` call must pass ``<caller>.id`` as its user."""
    problems = []
    for top in tree.body:
        if not isinstance(top, ast.AsyncFunctionDef | ast.FunctionDef):
            continue
        caller = _caller_param(top)
        for node in ast.walk(top):
            if not (
                isinstance(node, ast.Call) and dotted(node.func).endswith("usage_service.record")
            ):
                continue
            user = node.args[1] if len(node.args) > 1 else None
            user = user or next((k.value for k in node.keywords if k.arg == "user_id"), None)
            if caller is None or user is None or dotted(user) != f"{caller}.id":
                got = ast.unparse(user) if user is not None else None
                problems.append(f"{module}:{node.lineno} in {top.name}(): user={got}")
    return problems


def test_floor1_every_usage_record_uses_the_callers_id():
    problems, sites = [], 0
    for path in sorted(APP_ROOT.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "usage_service" not in source:
            continue
        module = rel(path)
        if module == "app/services/usage_service.py":
            continue
        tree = parse(path)
        sites += source.count("usage_service.record(")
        if not module.startswith("app/api/"):
            problems.append(f"{module}: records usage outside a request handler")
            continue
        problems += usage_record_problems(tree, module)
    assert sites >= 8, f"usage record sweep found only {sites} call sites; detector broken?"
    assert not problems, "usage events not keyed on the caller:\n" + "\n".join(problems)


def test_floor1_usage_record_detector_is_red_on_another_users_id():
    good = (
        "async def h(user: User = Depends(get_current_user_or_default)):\n"
        "    await usage_service.record(session, user.id, 'x')\n"
    )
    bad_pos = good.replace("user.id, 'x'", "body.owner_id, 'x'")
    bad_kw = good.replace("session, user.id, 'x'", "session, event='x', user_id=other.id")
    no_caller = good.replace("Depends(get_current_user_or_default)", "None")
    assert usage_record_problems(ast.parse(good), "m") == []
    for bad in (bad_pos, bad_kw, no_caller):
        assert usage_record_problems(ast.parse(bad), "m"), bad


# ── admin aggregates ───────────────────────────────────────────────────

ADMIN_AGGREGATES = {
    ("app.services.ai_feedback_service", "admin_summary"): (
        "app/api/ai_feedback.py",
        "admin_ai_feedback",
    ),
    ("app.services.usage_service", "retention_readout"): ("app/api/usage.py", "retention"),
}


def _references(function: str) -> set[tuple[str, str]]:
    found = set()
    for path in sorted(APP_ROOT.rglob("*.py")):
        tree = parse(path)
        for top in tree.body:
            if not isinstance(top, ast.AsyncFunctionDef | ast.FunctionDef):
                continue
            for node in ast.walk(top):
                name = node.attr if isinstance(node, ast.Attribute) else getattr(node, "id", None)
                if name == function:
                    found.add((rel(path), top.name))
    return found


@pytest.mark.parametrize(("target", "handler"), list(ADMIN_AGGREGATES.items()))
def test_floor1_admin_aggregates_are_called_only_from_their_admin_route(target, handler):
    _module, function = target
    refs = _references(function) - {(f"app/services/{_module.rsplit('.', 1)[-1]}.py", function)}
    assert refs == {handler}, f"{function} is referenced outside its admin route: {refs}"


def _admin_gated(route) -> bool:
    def walk(dependant):
        for dep in dependant.dependencies:
            if getattr(dep.call, "__qualname__", "") == "require_role.<locals>._check_role":
                roles = inspect.getclosurevars(dep.call).nonlocals.get("allowed_roles")
                if tuple(roles) == ("admin",):
                    return True
            if walk(dep):
                return True
        return False

    return walk(route.dependant)


@pytest.mark.parametrize(("target", "handler"), list(ADMIN_AGGREGATES.items()))
def test_floor1_admin_aggregate_routes_require_the_admin_role(target, handler):
    from fastapi.routing import APIRoute

    from app.main import app

    module, name = handler
    routes = [
        r
        for r in app.routes
        if isinstance(r, APIRoute)
        and inspect.unwrap(r.endpoint).__name__ == name
        and inspect.unwrap(r.endpoint).__module__ == module[:-3].replace("/", ".")
    ]
    assert routes, f"no live route for {handler}"
    for route in routes:
        assert _admin_gated(route), f"{route.path} lacks require_role('admin')"


def test_floor1_admin_gate_detector_is_red_without_the_role():
    from types import SimpleNamespace

    from app.api.deps import get_current_user, require_role

    plain = SimpleNamespace(
        dependant=SimpleNamespace(
            dependencies=[SimpleNamespace(call=get_current_user, dependencies=[])]
        )
    )
    user_role = SimpleNamespace(
        dependant=SimpleNamespace(
            dependencies=[SimpleNamespace(call=require_role("user", "admin"), dependencies=[])]
        )
    )
    admin = SimpleNamespace(
        dependant=SimpleNamespace(
            dependencies=[SimpleNamespace(call=require_role("admin"), dependencies=[])]
        )
    )
    assert not _admin_gated(plain)
    assert not _admin_gated(user_role)
    assert _admin_gated(admin)


def _walk_values(obj: Any):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _walk_values(v)
    elif isinstance(obj, list | tuple):
        for v in obj:
            yield from _walk_values(v)
    else:
        yield obj


@pytest.mark.asyncio
async def test_floor1_admin_feedback_summary_carries_no_user_identifier():
    from datetime import UTC, datetime

    from app.models.ai_feedback import AIFeedback
    from app.services import ai_feedback_service

    planted = AIFeedback(
        id="v-planted",
        user_id="floor1-planted-user-id",
        target_type="summary",
        target_id="floor1-planted-target",
        rating=-1,
        reason="unclear",
        comment="too vague",
        course_id="c-1",
    )
    planted.updated_at = datetime.now(UTC)
    results = [
        MagicMock(all=MagicMock(return_value=[("summary", -1, 1)])),
        MagicMock(all=MagicMock(return_value=[("unclear", 1)])),
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[planted])))),
    ]
    session = MagicMock()

    async def execute(_stmt):
        return results.pop(0)

    session.execute = execute
    out = await ai_feedback_service.admin_summary(session, days=30)
    flat = list(_walk_values(out))
    assert "floor1-planted-user-id" not in flat
    assert "floor1-planted-target" not in flat
    assert not IDENTIFYING & {k for k in flat if isinstance(k, str)}
    assert out["recent_negative"][0]["comment"] == "too vague"


def projected_identifiers(statement: Any) -> list[str]:
    """Bare identifying columns a statement projects (aggregates are fine)."""
    out = []
    for col in statement.selected_columns:
        inner = col.element if isinstance(col, Label) else col
        if isinstance(inner, FunctionElement):
            continue
        if isinstance(inner, ColumnClause) and (inner.name in IDENTIFYING or inner.name == "id"):
            out.append(str(inner))
    return out


@pytest.mark.asyncio
async def test_floor1_retention_readout_projects_no_user_identifier():
    from app.services import usage_service

    seen = []
    session = MagicMock()

    async def execute(stmt):
        seen.append(stmt)
        return MagicMock(all=MagicMock(return_value=[]))

    session.execute = execute
    out = await usage_service.retention_readout(session, weeks=4)
    assert len(seen) == 3
    for stmt in seen:
        assert projected_identifiers(stmt) == [], str(stmt)
    assert set(out) == {"cohorts", "features"}


def test_floor1_projection_detector_is_red_on_a_user_id():
    from sqlalchemy import func, select

    from app.models.usage_event import UsageEvent
    from app.models.user import User

    assert projected_identifiers(select(UsageEvent.user_id))
    assert projected_identifiers(select(User.email, func.count()))
    assert projected_identifiers(select(func.count(func.distinct(UsageEvent.user_id)))) == []

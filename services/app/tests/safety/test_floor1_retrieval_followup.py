"""Floors 1 and 3 (metering) for the GL#35 relevance floor and follow-up retrieval.

M33-S1-SAFETY-033 over ``a290904``/``e4adceb``/``3f5e506``. Pins:

* **floor 1**: every ``search_chunks`` call (and chat's ``_search`` wrapper)
  passes the caller's own id; a follow-up retrieval query folds in only the
  caller's own previous message from the caller's own session, and a foreign
  session id is refused before anything is embedded;
* **metering**: ``ai_called`` is False only on a path where the agent was not
  built. Structurally, ``get_agent`` sits only in the branch where
  ``plan.reply`` is None, ``ai_called`` is that same condition, computed after
  the last write to ``plan.reply``; the API skips ``record_ai_call`` only on an
  explicit False. Behaviourally, over MiniDB, a below-floor turn makes no agent
  and reports False, and an above-floor turn builds the agent and reports True.

Floor 3 needs no new pin: GL#35 adds no ``get_agent``/embedding call site, and
the ADR 0003 / ADR 0005 allowlist tests stay exact.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.safety._minidb import MiniDB, MiniSession
from tests.safety._source import APP_ROOT, dotted, parse, rel

USER_A = "floor1-retrieval-user-a"
USER_B = "floor1-retrieval-user-b"
CALLER_DEPENDENCIES = frozenset({"get_current_user", "get_current_user_or_default"})
SEARCH_CALLEES = frozenset({"search_chunks", "_search"})


# ── floor 1: the search always carries the caller ───────────────────────


def _caller_names(fn: ast.AsyncFunctionDef | ast.FunctionDef) -> set[str]:
    """Expressions that denote the caller inside ``fn``: ``user_id`` or ``<dep>.id``."""
    names: set[str] = set()
    args = fn.args
    params = [*args.posonlyargs, *args.args, *args.kwonlyargs]
    if any(a.arg == "user_id" for a in params):
        names.add("user_id")
    defaults = list(
        zip(args.args[len(args.args) - len(args.defaults) :], args.defaults, strict=True)
    )
    defaults += [(a, d) for a, d in zip(args.kwonlyargs, args.kw_defaults, strict=True) if d]
    for arg, default in defaults:
        if (
            isinstance(default, ast.Call)
            and dotted(default.func) == "Depends"
            and default.args
            and dotted(default.args[0]) in CALLER_DEPENDENCIES
        ):
            names.add(f"{arg.arg}.id")
    return names


def search_scope_problems(tree: ast.Module, module: str) -> list[str]:
    """Each search call's user must be the enclosing function's caller."""
    problems = []
    for top in ast.walk(tree):
        if not isinstance(top, ast.AsyncFunctionDef | ast.FunctionDef):
            continue
        callers = _caller_names(top)
        for node in ast.walk(top):
            if not isinstance(node, ast.Call):
                continue
            name = dotted(node.func).rsplit(".", 1)[-1]
            if name not in SEARCH_CALLEES:
                continue
            user = next((k.value for k in node.keywords if k.arg == "user_id"), None)
            if user is None and name == "_search" and len(node.args) > 1:
                user = node.args[1]
            if user is None or dotted(user) not in callers:
                got = ast.unparse(user) if user is not None else None
                problems.append(f"{module}:{node.lineno} in {top.name}(): user={got}")
    return problems


def test_floor1_every_chunk_search_carries_the_callers_id():
    problems, sites = [], 0
    for path in sorted(APP_ROOT.rglob("*.py")):
        module = rel(path)
        if module == "app/services/search_service.py":
            continue
        tree = parse(path)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and dotted(node.func).rsplit(".", 1)[-1] in SEARCH_CALLEES
            ):
                sites += 1
        problems += search_scope_problems(tree, module)
    assert sites >= 4, f"only {sites} search call sites found; detector broken?"
    assert not problems, "chunk searches not keyed on the caller:\n" + "\n".join(problems)


@pytest.mark.parametrize(
    "bad",
    [
        "async def f(session, user_id):\n    await search_service.search_chunks(session=session, user_id=other)\n",
        "async def f(session, user_id):\n    await _search(session, chat.user_id, plan, e)\n",
        "async def f(session):\n    await search_service.search_chunks(session=session)\n",
        "async def h(body, user=Depends(get_current_user_or_default)):\n"
        "    await search_service.search_chunks(user_id=body.user_id)\n",
    ],
)
def test_floor1_search_scope_detector_is_red_on(bad):
    assert search_scope_problems(ast.parse(bad), "m"), bad


def test_floor1_search_scope_detector_accepts_the_caller():
    ok = (
        "async def f(session, user_id):\n    await _search(session, user_id, plan, e)\n"
        "async def h(user=Depends(get_current_user_or_default)):\n"
        "    await search_service.search_chunks(user_id=user.id)\n"
    )
    assert search_scope_problems(ast.parse(ok), "m") == []


# ── MiniDB harness for chat turns ───────────────────────────────────────


class _Session(MiniSession):
    async def commit(self) -> None:
        return None

    async def refresh(self, *_a: Any, **_k: Any) -> None:
        return None


def _world() -> tuple[MiniDB, dict[str, str]]:
    from app.models.chat_message import ChatMessage
    from app.models.chat_session import ChatSession

    db = MiniDB()
    # B's messages are the newer ones, so a history query that lost its
    # session filter would pick B's question as "the previous message".
    for owner, tag, text, t0 in (
        (USER_A, "a", "A-previous question", datetime(2026, 1, 1, tzinfo=UTC)),
        (USER_B, "b", "B-secret text", datetime(2026, 1, 2, tzinfo=UTC)),
    ):
        db.add(
            ChatSession(id=f"chat-{tag}", user_id=owner, title="t", message_count=2, course_id=None)
        )
        db.add(
            ChatMessage(
                id=f"m-{tag}-1", session_id=f"chat-{tag}", role="user", content=text, created_at=t0
            )
        )
        db.add(
            ChatMessage(
                id=f"m-{tag}-2",
                session_id=f"chat-{tag}",
                role="assistant",
                content="ok",
                created_at=t0 + timedelta(seconds=1),
            )
        )
    return db, {"a": "chat-a", "b": "chat-b"}


def _patches(similarity: float):
    provider = MagicMock()
    provider.embed_texts = MagicMock(return_value=[[0.0, 1.0]])
    search = AsyncMock(
        return_value=[
            {
                "chunk_id": "c1",
                "content": "x",
                "similarity": similarity,
                "artifact_id": "art",
                "course_id": None,
                "week": None,
            }
        ]
    )
    agent = MagicMock()
    agent.answer_question = AsyncMock(return_value=SimpleNamespace(answer="an answer"))

    async def stream(*_a, **_k):
        yield "tok"

    agent.stream_answer = stream
    get_agent = MagicMock(return_value=agent)
    return provider, search, get_agent


async def _turn(db, session_id: str, similarity: float, *, stream: bool) -> dict[str, Any]:
    from app.services import chat_service

    provider, search, get_agent = _patches(similarity)
    with (
        patch.object(chat_service, "get_embedding_provider", return_value=provider),
        patch.object(chat_service.search_service, "search_chunks", search),
        patch.object(chat_service, "get_agent", get_agent),
        patch(
            "app.services.settings_service.get_user_ai_context",
            AsyncMock(return_value=(None, "en")),
        ),
        patch.object(chat_service, "build_sources", return_value=[]),
    ):
        session = _Session(db)
        content = "what about the second one?"
        if stream:
            events = [
                e
                async for e in chat_service.stream_message(
                    session=session, session_id=session_id, user_id=USER_A, content=content
                )
            ]
            flags = [e["ai_called"] for e in events if "ai_called" in e]
            ai_called = flags[-1] if flags else None
        else:
            _user_msg, assistant = await chat_service.send_message(
                session, session_id, USER_A, content
            )
            ai_called = assistant.ai_called
    return {
        "embedded": [c.args[0] for c in provider.embed_texts.call_args_list],
        "search": search,
        "get_agent": get_agent,
        "ai_called": ai_called,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
async def test_floor1_followup_query_uses_only_the_callers_own_history(stream):
    db, ids = _world()
    out = await _turn(db, ids["a"], 0.9, stream=stream)
    embedded = "\n".join(t for batch in out["embedded"] for t in batch)
    assert "A-previous question" in embedded, embedded
    assert "B-secret" not in embedded
    assert out["search"].await_args.kwargs["user_id"] == USER_A


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
async def test_floor1_foreign_session_is_refused_before_any_embedding(stream):
    """send_message raises; stream_message yields its error event and stops."""
    from app.services import chat_service

    db, ids = _world()
    provider, search, get_agent = _patches(0.9)
    with (
        patch.object(chat_service, "get_embedding_provider", return_value=provider),
        patch.object(chat_service.search_service, "search_chunks", search),
        patch.object(chat_service, "get_agent", get_agent),
    ):
        session = _Session(db)
        if stream:
            events = [
                e
                async for e in chat_service.stream_message(
                    session=session, session_id=ids["b"], user_id=USER_A, content="q"
                )
            ]
            assert [e["event"] for e in events] == ["error"]
        else:
            with pytest.raises(ValueError):
                await chat_service.send_message(session, ids["b"], USER_A, "q")
    assert not provider.embed_texts.called
    assert not search.called and not get_agent.called
    assert [o.id for o in db.rows["chat_messages"]] == ["m-a-1", "m-a-2", "m-b-1", "m-b-2"]


# ── metering: ai_called is False only when no agent was built ──────────


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize(("similarity", "expect_ai"), [(0.01, False), (0.9, True)])
async def test_floor3_ai_called_matches_whether_the_agent_was_built(stream, similarity, expect_ai):
    db, ids = _world()
    out = await _turn(db, ids["a"], similarity, stream=stream)
    assert out["get_agent"].called is expect_ai
    assert out["ai_called"] is expect_ai


def _function(tree: ast.Module, name: str) -> ast.AsyncFunctionDef:
    return next(
        n
        for n in tree.body
        if isinstance(n, ast.AsyncFunctionDef | ast.FunctionDef) and n.name == name
    )


def ai_flag_problems(fn: ast.AST) -> list[str]:
    """``ai_called`` must equal "no fixed reply", fixed after the last reply write,
    and the agent must be built only when there is no fixed reply."""
    problems = []
    flag_assigns = [
        n
        for n in ast.walk(fn)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "ai_called" for t in n.targets)
    ]
    if len(flag_assigns) != 1:
        problems.append(f"ai_called assigned {len(flag_assigns)} times")
        return problems
    (flag,) = flag_assigns
    if ast.unparse(flag.value) != "plan.reply is None":
        problems.append(f"ai_called = {ast.unparse(flag.value)}")
    late_reply = [
        n.lineno
        for n in ast.walk(fn)
        if isinstance(n, ast.Assign)
        and any(ast.unparse(t) == "plan.reply" for t in n.targets)
        and n.lineno > flag.lineno
    ]
    if late_reply:
        problems.append(f"plan.reply written after ai_called at {late_reply}")
    guarded: set[int] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.If) and ast.unparse(node.test) == "plan.reply is not None":
            for stmt in node.orelse:
                guarded |= {id(n) for n in ast.walk(stmt)}
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Call)
            and dotted(node.func).rsplit(".", 1)[-1] == "get_agent"
            and id(node) not in guarded
        ):
            problems.append(f"get_agent at line {node.lineno} outside the no-reply branch")
    return problems


@pytest.mark.parametrize("name", ["send_message", "stream_message"])
def test_floor3_ai_called_flag_is_tied_to_the_agent_branch(name):
    tree = parse(APP_ROOT / "services" / "chat_service.py")
    assert ai_flag_problems(_function(tree, name)) == []


@pytest.mark.parametrize(
    "bad",
    [
        "async def f():\n    ai_called = False\n    if plan.reply is not None:\n        x = 1\n"
        "    else:\n        get_agent()\n",
        "async def f():\n    ai_called = plan.reply is None\n    plan.reply = 'x'\n"
        "    if plan.reply is not None:\n        x = 1\n    else:\n        get_agent()\n",
        "async def f():\n    ai_called = plan.reply is None\n    get_agent()\n",
    ],
)
def test_floor3_ai_flag_detector_is_red_on(bad):
    assert ai_flag_problems(_function(ast.parse(bad), "f")), bad


def test_floor3_chat_api_skips_metering_only_on_an_explicit_false():
    """``record_ai_call`` is guarded by ``is not False`` / a flag only a False event clears."""
    tree = parse(APP_ROOT / "api" / "chat.py")
    guards = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and any(
            isinstance(n, ast.Call) and dotted(n.func).endswith("record_ai_call")
            for s in node.body
            for n in ast.walk(s)
        ):
            guards.append(ast.unparse(node.test))
    assert sorted(guards) == sorted(
        ["getattr(assistant_msg, 'ai_called', True) is not False", "ai_called"]
    ), guards
    stream = _function(tree, "stream_message")
    clears = [
        ast.unparse(n)
        for n in ast.walk(stream)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "ai_called" for t in n.targets)
    ]
    assert sorted(clears) == ["ai_called = False", "ai_called = True"], clears
    false_set = next(
        n
        for n in ast.walk(stream)
        if isinstance(n, ast.If) and any(ast.unparse(s) == "ai_called = False" for s in n.body)
    )
    assert ast.unparse(false_set.test) == "event.get('ai_called') is False"

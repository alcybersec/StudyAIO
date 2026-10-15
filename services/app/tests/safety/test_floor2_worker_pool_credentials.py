"""Floor 2 x floor 3 — the Claude login goes only to the pools that call the agent.

GL#51 (M33-S3-DEVOPS-030) split the one Celery worker into three compose
services, one per queue family (``app/worker.py`` ``_QUEUE_TASKS``):

* ``worker`` consumes ``pipeline`` (+ the legacy ``celery`` drain);
* ``worker-ondemand`` consumes ``ai_ondemand``;
* ``worker-maintenance`` consumes ``maintenance`` and gets no Claude login.

``CLAUDE_LOGIN_SERVICES`` in ``test_floor2_claude_login_mounts`` is the floor-2
allowlist of services that may see the login. These pins tie it to the routing,
so neither side can drift alone (M33-S3-SAFETY-059):

* every allowlisted service consumes at least one queue with a task that reaches
  ``get_agent`` — a login handed to a pool that never calls the agent is a
  credential with no purpose (the revert check: add the mounts to
  ``worker-maintenance`` and both this and the mount pin fail);
* no task routed to a queue that only non-allowlisted services consume reaches
  ``get_agent`` — so ``worker-maintenance`` holding no login is sound (re-embed
  reaches ``get_embedding_provider``, an operator-wide gateway, not the agent);
* the call graph is not blind: it finds ``get_agent`` from each pool's known AI
  tasks and finds ``get_embedding_provider`` from re-embed.

Static: ``app/worker.py`` and the pipeline are parsed, not imported.
"""

from __future__ import annotations

import ast
import re

import pytest

from tests.safety import _callgraph as cg
from tests.safety._source import APP_ROOT, parse
from tests.safety.test_floor2_claude_login_mounts import (
    BASE,
    CLAUDE_LOGIN_SERVICES,
    REPO_ROOT,
    _compose_files,
    _load,
    _untag,
)

GET_AGENT: cg.Node = ("app.agents.factory", "get_agent")
GET_EMBEDDING_PROVIDER: cg.Node = ("app.agents.embeddings", "get_embedding_provider")

#: Tasks the graph must see reaching the agent (guards the guard).
KNOWN_AI_TASKS = {
    "app.pipeline.classify.classify_artifact",
    "app.pipeline.summarize.summarize_artifact",
    "app.pipeline.assets.generate_assets",
    "app.pipeline.courseops_task.process_course_document",
    "app.pipeline.targeted_task.generate_targeted_items",
    "app.pipeline.concepts_task.extract_concepts",
}


def _queue_tasks() -> dict[str, tuple[str, ...]]:
    """``_QUEUE_TASKS`` from ``app/worker.py``, evaluated from source."""
    tree = parse(APP_ROOT / "worker.py")
    consts: dict[str, str] = {}
    table = None
    for stmt in tree.body:
        targets = [stmt.target] if isinstance(stmt, ast.AnnAssign) else getattr(stmt, "targets", [])
        names = [t.id for t in targets if isinstance(t, ast.Name)]
        value = getattr(stmt, "value", None)
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            consts.update(dict.fromkeys(names, value.value))
        if "_QUEUE_TASKS" in names:
            table = value
    assert isinstance(table, ast.Dict), "app/worker.py lost _QUEUE_TASKS; update this pin"
    out = {}
    for key, val in zip(table.keys, table.values, strict=True):
        queue = consts[key.id] if isinstance(key, ast.Name) else ast.literal_eval(key)
        out[queue] = tuple(ast.literal_eval(val))
    return out


_Q = re.compile(r"(?:^|\s)(?:-Q|--queues)[ =](\S+)")


def _service_queues() -> dict[str, set[str]]:
    """Compose service -> queues its ``celery worker`` command consumes (all files)."""
    out: dict[str, set[str]] = {}
    for path in _compose_files():
        for name, service in (_load(path).get("services") or {}).items():
            command = _untag((service or {}).get("command"))
            if isinstance(command, list):
                command = " ".join(map(str, command))
            if not command or "worker" not in str(command).split():
                continue
            m = _Q.search(str(command))
            # A worker with no -Q consumes the default queues: treat as "everything".
            queues = set(m[1].split(",")) if m else {"*"}
            out.setdefault(name, set()).update(queues)
    return out


@pytest.fixture(scope="module")
def routing() -> dict[str, tuple[str, ...]]:
    return _queue_tasks()


def _reaches(task: str, target: cg.Node) -> bool:
    return target in cg.reachable(cg.task_node(task))


def test_floor2_pool_guard_parses_routing_and_compose(routing):
    """Guard the guard: the queue table and the base pools are what GL#51 shipped."""
    assert {"pipeline", "ai_ondemand", "maintenance"} <= set(routing)
    for queue, tasks in routing.items():
        for task in tasks:
            module, func = cg.task_node(task)
            mod = cg.load(module)
            assert mod is not None and func in mod.tasks, (
                f"{queue}: {task} is not a Celery task defined in {module}"
            )
    queues = _service_queues()
    base = {n for n in (_load(REPO_ROOT / BASE).get("services") or {}) if n in queues}
    assert {"worker", "worker-ondemand", "worker-maintenance"} <= base, queues


def test_floor2_pool_call_graph_is_not_blind(routing):
    """Every known AI task reaches get_agent; re-embed reaches the embedding gateway."""
    routed = {t for tasks in routing.values() for t in tasks}
    missing = sorted(KNOWN_AI_TASKS - routed)
    assert not missing, f"known AI tasks no longer routed (update KNOWN_AI_TASKS): {missing}"
    blind = sorted(t for t in KNOWN_AI_TASKS if not _reaches(t, GET_AGENT))
    assert not blind, f"call graph no longer sees get_agent from {blind}"
    assert _reaches("app.pipeline.reembed_task.reembed_user_chunks", GET_EMBEDDING_PROVIDER)
    # ...and ``.delay()`` is not an edge: the fan-out task enqueues, it does not embed.
    assert not _reaches("app.pipeline.reembed_task.reembed_all_chunks", GET_EMBEDDING_PROVIDER)
    assert ("app.pipeline.orchestrator", "resume_pipeline") in cg.reachable(
        cg.task_node("app.pipeline.recovery.recover_stuck_artifacts")
    ), "recovery no longer resolves its function-local import; the graph is blind there"


def test_floor2_maintenance_tasks_never_reach_the_agent(routing):
    """Nothing routed to ``maintenance`` calls ``get_agent`` (it runs with no login)."""
    bad = sorted(t for t in routing["maintenance"] if _reaches(t, GET_AGENT))
    assert not bad, (
        "Floor 3/2: a maintenance-queue task reaches get_agent, but worker-maintenance has "
        f"no Claude login (GL#51). Route it to pipeline/ai_ondemand instead: {bad}"
    )


def test_floor2_claude_login_only_where_the_agent_is_called(routing):
    """Allowlisted pools consume an AI queue; AI queues are consumed only by them."""
    ai_queues = {q for q, tasks in routing.items() if any(_reaches(t, GET_AGENT) for t in tasks)}
    pools = _service_queues()
    bad = []
    for svc in sorted(CLAUDE_LOGIN_SERVICES):
        consumed = pools.get(svc, set())
        if "*" not in consumed and not consumed & ai_queues:
            bad.append(f"{svc} holds the Claude login but consumes no AI queue ({consumed})")
    for svc, consumed in sorted(pools.items()):
        if svc in CLAUDE_LOGIN_SERVICES:
            continue
        hit = sorted(consumed & ai_queues) if "*" not in consumed else sorted(ai_queues)
        if hit:
            bad.append(f"{svc} consumes AI queue(s) {hit} with no Claude login")
    assert not bad, "Floor 2 (R-025, GL#51):\n" + "\n".join(bad)

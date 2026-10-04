"""Floor 3 — AI only via the adapter.

    every AI call goes through AgentAdapter, obtained via `get_agent`;
    `get_agent` is called only in `app/pipeline/**` (the Celery worker) and at
    the request-time call sites enumerated in ADR 0003, and a new request-time
    call site requires amending that ADR.

The four checks are the ones ADR 0003 "Consequences" specifies, in its order.
All are static (AST) and need no services.

Scope note — embeddings (R-004): ``app/agents/embeddings.py`` reaches a remote
model through ``EmbeddingProvider``, not ``AgentAdapter``. Its SDK imports sit
inside ``app/agents/**``, so check 2 does not see it, and none of these tests
constrain where ``get_embedding_provider`` is called. That is deliberate until
the user rules on R-004; ``FLOORS.md`` records what each ruling would add.
"""

from __future__ import annotations

import ast

from tests.safety._source import (
    Site,
    app_modules,
    docstring_nodes,
    dotted,
    parse,
    rel,
    walk_with_scope,
)

# Verbatim from docs/adr/0003-floor3-request-time-ai-calls.md, Decision 2.
# Changing this set is changing the floor: it needs an ADR amendment and the
# user's agreement, not a drive-by edit here.
REQUEST_TIME_GET_AGENT_CALL_SITES = {
    ("app/api/qa.py", "ask_question"),
    ("app/api/settings.py", "test_ai_connection"),
    ("app/services/chat_service.py", "send_message"),
    ("app/services/chat_service.py", "stream_message"),
    ("app/services/concept_service.py", "extract_and_save_concepts"),
}

PROVIDER_SDKS = frozenset({"anthropic", "openai", "ollama"})

ADAPTER_CLASSES = frozenset(
    {
        "ClaudeCodeAdapter",
        "AnthropicAPIAdapter",
        "OpenAIAdapter",
        "ZaiAdapter",
        "OllamaAdapter",
    }
)

FACTORY_MODULES = frozenset({"app.agents.factory", "app.agents"})

#: Calls that start a process. Matched on the dotted callee text.
SPAWN_CALLEES = frozenset(
    {
        "subprocess.run",
        "subprocess.Popen",
        "subprocess.call",
        "subprocess.check_call",
        "subprocess.check_output",
        "asyncio.create_subprocess_exec",
        "asyncio.create_subprocess_shell",
        "os.system",
        "os.popen",
        "os.execv",
        "os.execvp",
        "os.execve",
        "os.execl",
        "os.execlp",
        "os.spawnv",
        "os.spawnvp",
        "os.posix_spawn",
        "os.posix_spawnp",
        "pty.spawn",
    }
)

AGENTS = "app/agents/"
PIPELINE = "app/pipeline/"


# ── collectors ─────────────────────────────────────────────────────────


def _get_agent_aliases(tree: ast.Module) -> tuple[set[str], set[str]]:
    """Names bound to ``get_agent`` and to the factory module in this file."""
    func_names = {"get_agent"}
    module_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in FACTORY_MODULES:
            for alias in node.names:
                if alias.name == "get_agent":
                    func_names.add(alias.asname or alias.name)
                if alias.name == "factory":
                    module_names.add(alias.asname or alias.name)
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in FACTORY_MODULES:
                    module_names.add(alias.asname or alias.name)
    return func_names, module_names


def get_agent_sites(*, under: str | None = None, exclude: tuple[str, ...] = ()) -> list[Site]:
    """Every call to ``get_agent`` (any alias, any qualification)."""
    sites = []
    for path in app_modules(exclude=exclude):
        module = rel(path)
        if under is not None and not module.startswith(under):
            continue
        tree = parse(path)
        func_names, _modules = _get_agent_aliases(tree)
        for node, scope in walk_with_scope(tree):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            hit = (isinstance(f, ast.Name) and f.id in func_names) or (
                isinstance(f, ast.Attribute) and f.attr == "get_agent"
            )
            if hit:
                sites.append(Site(module, scope, node.lineno, ast.unparse(node)[:80]))
    return sites


def request_time_get_agent_sites() -> set[tuple[str, str]]:
    """ADR 0003 check 1: (module, function) pairs outside agents/ and pipeline/."""
    return {s.key() for s in get_agent_sites(exclude=(AGENTS, PIPELINE))}


def provider_sdk_imports() -> list[Site]:
    """ADR 0003 check 2a: provider SDK imports outside ``app/agents/**``."""
    sites = []
    for path in app_modules(exclude=(AGENTS,)):
        tree = parse(path)
        for node, scope in walk_with_scope(tree):
            roots: list[str] = []
            if isinstance(node, ast.Import):
                roots = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots = [node.module.split(".")[0]]
            elif (
                isinstance(node, ast.Call)
                and dotted(node.func) in {"importlib.import_module", "__import__"}
                and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                roots = [str(node.args[0].value).split(".")[0]]
            for root in roots:
                if root in PROVIDER_SDKS:
                    sites.append(Site(rel(path), scope, node.lineno, ast.unparse(node)[:80]))
    return sites


def adapter_class_references() -> list[Site]:
    """ADR 0003 check 2b: adapter class names outside ``app/agents/**``.

    Names, attributes, imported names, and string literals equal to a class
    name (a ``getattr(module, "OpenAIAdapter")`` is a reference too). Comments
    are invisible to ``ast``; docstrings are skipped explicitly.
    """
    sites = []
    for path in app_modules(exclude=(AGENTS,)):
        tree = parse(path)
        docs = docstring_nodes(tree)
        for node, scope in walk_with_scope(tree):
            name = None
            if isinstance(node, ast.Name):
                name = node.id
            elif isinstance(node, ast.Attribute):
                name = node.attr
            elif isinstance(node, ast.alias):
                name = node.asname or node.name.split(".")[-1]
                if node.name.split(".")[-1] in ADAPTER_CLASSES:
                    name = node.name.split(".")[-1]
            elif (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docs
            ):
                name = node.value.strip()
            if name in ADAPTER_CLASSES:
                line = getattr(node, "lineno", 0)
                sites.append(Site(rel(path), scope, line, name))
    return sites


def _mentions_claude_cli(node: ast.AST) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            v = sub.value.strip()
            first = v.split()[0] if v.split() else ""
            if first == "claude" or first.endswith("/claude"):
                return True
        if isinstance(sub, ast.Attribute) and sub.attr == "claude_code_path":
            return True
        if isinstance(sub, ast.Name) and sub.id == "claude_code_path":
            return True
    return False


def claude_cli_spawns() -> list[Site]:
    """ADR 0003 check 2c: a process whose program is the claude CLI, outside agents/."""
    sites = []
    for path in app_modules(exclude=(AGENTS,)):
        tree = parse(path)
        for node, scope in walk_with_scope(tree):
            if not isinstance(node, ast.Call):
                continue
            callee = dotted(node.func)
            if callee not in SPAWN_CALLEES and not callee.endswith(
                (".create_subprocess_exec", ".create_subprocess_shell")
            ):
                continue
            # Only the program position decides: args[0] (or the first element
            # of an argv list). Keyword args such as env= may legitimately carry
            # unrelated strings.
            program = node.args[0] if node.args else None
            if isinstance(program, ast.List | ast.Tuple) and program.elts:
                program = program.elts[0]
            if isinstance(program, ast.Starred):
                program = program.value
            if program is not None and _mentions_claude_cli(program):
                sites.append(Site(rel(path), scope, node.lineno, ast.unparse(node)[:80]))
    return sites


def _registers_celery_task(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for dec in node.decorator_list:
            target = dec.func if isinstance(dec, ast.Call) else dec
            text = dotted(target)
            if text.endswith(".task") or text in {"shared_task", "task"}:
                return True
    return False


def pipeline_get_agent_outside_task_modules() -> list[Site]:
    """ADR 0003 check 3: pipeline get_agent calls in a module with no Celery task."""
    bad = []
    by_module: dict[str, list[Site]] = {}
    for s in get_agent_sites(under=PIPELINE):
        by_module.setdefault(s.module, []).append(s)
    for path in app_modules():
        module = rel(path)
        if module in by_module and not _registers_celery_task(parse(path)):
            bad.extend(by_module[module])
    return bad


# ── tests ──────────────────────────────────────────────────────────────


def test_floor3_request_time_get_agent_sites_equal_adr_0003_allowlist():
    """Check 1: the request-time get_agent sites are exactly ADR 0003's list."""
    found = request_time_get_agent_sites()
    extra = sorted(found - REQUEST_TIME_GET_AGENT_CALL_SITES)
    missing = sorted(REQUEST_TIME_GET_AGENT_CALL_SITES - found)
    assert not extra and not missing, (
        "Floor 3: request-time get_agent call sites differ from ADR 0003.\n"
        f"  new, not in the ADR (amend ADR 0003 with the user, or move it to the worker): {extra}\n"
        f"  in the ADR, no longer found (amend ADR 0003 to drop it): {missing}"
    )


def test_floor3_no_provider_sdk_import_outside_agents():
    """Check 2a: anthropic / openai / ollama are imported only under app/agents/."""
    sites = provider_sdk_imports()
    assert not sites, "Floor 3: provider SDK imported outside app/agents/**:\n" + "\n".join(
        f"  {s}" for s in sites
    )


def test_floor3_no_adapter_class_reference_outside_agents():
    """Check 2b: adapters are constructed only through get_agent."""
    sites = adapter_class_references()
    assert not sites, "Floor 3: adapter class referenced outside app/agents/**:\n" + "\n".join(
        f"  {s}" for s in sites
    )


def test_floor3_no_claude_cli_spawn_outside_agents():
    """Check 2c: only app/agents/** starts the claude CLI."""
    sites = claude_cli_spawns()
    assert not sites, "Floor 3: claude CLI spawned outside app/agents/**:\n" + "\n".join(
        f"  {s}" for s in sites
    )


def test_floor3_pipeline_get_agent_only_in_celery_task_modules():
    """Check 3: every pipeline get_agent call is in a module that registers a task."""
    sites = pipeline_get_agent_outside_task_modules()
    assert not sites, (
        "Floor 3: get_agent called under app/pipeline/ in a module with no Celery task:\n"
        + "\n".join(f"  {s}" for s in sites)
    )


def test_floor3_detectors_are_not_vacuous():
    """The collectors find what is known to be there.

    A detector that silently stops matching (a renamed helper, a path change)
    turns every test above into a pass. Pin the positive cases.
    """
    pipeline_modules = {s.module for s in get_agent_sites(under=PIPELINE)}
    assert {
        "app/pipeline/classify.py",
        "app/pipeline/summarize.py",
        "app/pipeline/assets.py",
        "app/pipeline/courseops_task.py",
    } <= pipeline_modules
    # The SDK and adapter detectors do find the real ones inside app/agents/.
    from tests.safety import _source

    agents_hits = [
        p
        for p in _source.app_modules()
        if rel(p).startswith(AGENTS)
        and any(
            isinstance(n, ast.Import | ast.ImportFrom)
            and (
                (isinstance(n, ast.ImportFrom) and (n.module or "").split(".")[0] in PROVIDER_SDKS)
                or (
                    isinstance(n, ast.Import)
                    and any(a.name.split(".")[0] in PROVIDER_SDKS for a in n.names)
                )
            )
            for n in ast.walk(parse(p))
        )
    ]
    assert agents_hits, "SDK import detector found nothing even inside app/agents/"

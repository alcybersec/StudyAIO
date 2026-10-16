"""Floor 3 — AI only via the adapter.

    every AI call goes through a sanctioned gateway, either AgentAdapter
    obtained via `get_agent`, or, for embeddings, EmbeddingProvider obtained via
    `get_embedding_provider`; outside `app/agents/**` and `app/pipeline/**` (the
    Celery worker), each gateway is called only at the call sites enumerated in
    ADR 0003 (`get_agent`) and ADR 0005 (`get_embedding_provider`), and a new
    such call site requires amending the ADR that lists it.

The first group of checks is ADR 0003's "Consequences", in its order. The
second group is ADR 0005's "What safety adds", items 1-7, for the embedding
gateway. All are static (AST) and need no services.
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

#: ADR 0003 bans the first three; ADR 0005 §4 adds the local embedding SDK.
PROVIDER_SDKS = frozenset({"anthropic", "openai", "ollama", "sentence_transformers"})

# ── ADR 0005: the embedding gateway ────────────────────────────────────
# Verbatim from docs/adr/0005-floor3-embedding-gateway.md, Decision 3. As with
# ADR 0003's list, changing one of these sets is changing the floor.

#: Callers of `get_embedding_provider` outside app/agents/** and app/pipeline/**.
GET_EMBEDDING_PROVIDER_CALL_SITES = {
    ("app/api/qa.py", "ask_question"),
    ("app/services/chat_service.py", "send_message"),
    ("app/services/chat_service.py", "stream_message"),
    ("app/services/concept_service.py", "_embed_concepts"),
    ("app/main.py", "warn_if_embedding_provider_unavailable"),
}

#: Callers of `.embed_texts(...)`, or of its async wrapper `aembed_texts(provider, ...)`,
#: outside app/agents/** and app/pipeline/**. `aembed_texts` lives in app/agents/**, so
#: its own `provider.embed_texts` is out of scan; without counting its callers a new
#: request-side `await aembed_texts(...)` would embed past this pin unseen.
EMBED_TEXTS_CALL_SITES = {
    ("app/api/qa.py", "ask_question"),
    ("app/services/chat_service.py", "send_message"),
    ("app/services/chat_service.py", "stream_message"),
    ("app/services/concept_service.py", "_embed_concepts"),
    ("app/services/index_service.py", "embed_artifact_chunks"),
    ("app/services/index_service.py", "aembed_artifact_chunks"),
}

#: The names that embed: the provider method and the agents-side async wrapper.
EMBED_NAMES = frozenset({"embed_texts", "aembed_texts"})

#: Startup-only sites: may call `get_embedding_provider` and `.preload()`, never `.embed_texts`.
STARTUP_ONLY_EMBEDDING_SITES = {
    ("app/main.py", "warn_if_embedding_provider_unavailable"),
}

#: A function that embeds with an injected provider -> the only callers it may have.
#: Every allowed caller is under app/pipeline/** or is itself a key here, so each
#: chain of injected-provider calls ends in the worker. Subset, not equality: a
#: caller going away is safe; a new one is the breach. (M34-S3-AI-010 split
#: `index_artifact_chunks` into embed + store; the wrapper stays until the stage
#: moves to `aembed_artifact_chunks` + `store_artifact_chunks`.)
INJECTED_PROVIDER_CALLERS = {
    ("app/services/index_service.py", "index_artifact_chunks"): {
        ("app/pipeline/index.py", "_index"),
    },
    ("app/services/index_service.py", "embed_artifact_chunks"): {
        ("app/services/index_service.py", "index_artifact_chunks"),
        ("app/pipeline/index.py", "_index"),
    },
    ("app/services/index_service.py", "aembed_artifact_chunks"): {
        ("app/pipeline/index.py", "_index"),
    },
}

#: ADR 0005 §4: never referenced outside app/agents/** (docstrings and comments aside).
EMBEDDING_PROVIDER_CLASSES = frozenset(
    {"SentenceTransformerProvider", "OpenAIEmbeddingProvider", "OllamaEmbeddingProvider"}
)
EMBEDDING_TEST_SEAMS = frozenset({"reset_embedding_provider"})
EMBEDDING_BASE_CLASS = "EmbeddingProvider"
EMBEDDING_MODULES = frozenset({"app.agents.embeddings", "app.agents"})

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


def name_references(names: frozenset[str], *, exclude: tuple[str, ...] = (AGENTS,)) -> list[Site]:
    """Every reference to one of ``names`` outside ``exclude``.

    Names, attributes, imported names, and string literals equal to a name (a
    ``getattr(module, "OpenAIAdapter")`` is a reference too). Comments are
    invisible to ``ast``; docstrings are skipped explicitly.
    """
    sites = []
    for path in app_modules(exclude=exclude):
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
                if node.name.split(".")[-1] in names:
                    name = node.name.split(".")[-1]
            elif (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docs
            ):
                name = node.value.strip()
            if name in names:
                line = getattr(node, "lineno", 0)
                sites.append(Site(rel(path), scope, line, name))
    return sites


def adapter_class_references() -> list[Site]:
    """ADR 0003 check 2b: adapter class names outside ``app/agents/**``."""
    return name_references(ADAPTER_CLASSES)


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


# ── collectors: the embedding gateway (ADR 0005) ───────────────────────


def _embedding_factory_aliases(tree: ast.Module) -> set[str]:
    """Local names bound to ``get_embedding_provider`` in this file."""
    names = {"get_embedding_provider"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in EMBEDDING_MODULES:
            for alias in node.names:
                if alias.name == "get_embedding_provider":
                    names.add(alias.asname or alias.name)
    return names


def get_embedding_provider_sites(
    *, under: str | None = None, exclude: tuple[str, ...] = ()
) -> list[Site]:
    """Every *reference* to ``get_embedding_provider``, call or not.

    A reference rather than a call, because ``Depends(get_embedding_provider)``
    or a stored ``factory = get_embedding_provider`` reaches the gateway just as
    well. Import statements bind the name; they are not sites.
    """
    sites = []
    for path in app_modules(exclude=exclude):
        module = rel(path)
        if under is not None and not module.startswith(under):
            continue
        tree = parse(path)
        aliases = _embedding_factory_aliases(tree)
        for node, scope in walk_with_scope(tree):
            hit = (isinstance(node, ast.Name) and node.id in aliases) or (
                isinstance(node, ast.Attribute) and node.attr == "get_embedding_provider"
            )
            if hit:
                sites.append(Site(module, scope, node.lineno, ast.unparse(node)[:80]))
    return sites


def request_side_get_embedding_provider_sites() -> set[tuple[str, str]]:
    """ADR 0005 item 1: (module, function) pairs outside agents/ and pipeline/."""
    return {s.key() for s in get_embedding_provider_sites(exclude=(AGENTS, PIPELINE))}


def embed_texts_sites(*, exclude: tuple[str, ...] = (AGENTS, PIPELINE)) -> list[Site]:
    """ADR 0005 item 2: every reference to an embed name, and the names as strings.

    ``.embed_texts`` as an attribute, not only a call: ``fn = provider.embed_texts``
    then ``fn(x)`` embeds as surely as ``provider.embed_texts(x)``. ``aembed_texts``
    as a name or attribute: it embeds with the provider it is handed, from inside
    app/agents/** where the scan does not look. A string catches ``getattr``.
    Import statements bind names; they are not sites.
    """
    sites = []
    for path in app_modules(exclude=exclude):
        tree = parse(path)
        docs = docstring_nodes(tree)
        for node, scope in walk_with_scope(tree):
            if (
                (isinstance(node, ast.Attribute) and node.attr in EMBED_NAMES)
                or (isinstance(node, ast.Name) and node.id == "aembed_texts")
                or (
                    isinstance(node, ast.Constant)
                    and node.value in EMBED_NAMES
                    and id(node) not in docs
                )
            ):
                sites.append(Site(rel(path), scope, node.lineno, ast.unparse(node)[:80]))
    return sites


def references_to(module_name: str, function: str) -> set[tuple[str, str]]:
    """(module, enclosing function) of every reference to ``function`` under app/.

    Matched on the name (``function`` or ``<anything>.function``), which
    over-reports rather than under-reports: a same-named function elsewhere
    shows up as an extra caller and fails the pin, never hides one. The
    definition in ``module_name`` is a ``def``, not a reference.
    """
    out = set()
    for path in app_modules():
        for node, scope in walk_with_scope(parse(path)):
            if (isinstance(node, ast.Name) and node.id == function) or (
                isinstance(node, ast.Attribute) and node.attr == function
            ):
                out.add((rel(path), scope))
    return out


def pipeline_get_embedding_provider_outside_task_modules() -> list[Site]:
    """ADR 0005 item 5: ADR 0003 check 3, applied to the embedding gateway."""
    by_module: dict[str, list[Site]] = {}
    for s in get_embedding_provider_sites(under=PIPELINE):
        by_module.setdefault(s.module, []).append(s)
    bad = []
    for path in app_modules():
        module = rel(path)
        if module in by_module and not _registers_celery_task(parse(path)):
            bad.extend(by_module[module])
    return bad


def embedding_provider_subclasses() -> list[Site]:
    """ADR 0005 §4: a class outside ``app/agents/**`` deriving from EmbeddingProvider."""
    sites = []
    for path in app_modules(exclude=(AGENTS,)):
        for node, scope in walk_with_scope(parse(path)):
            if isinstance(node, ast.ClassDef) and any(
                dotted(b).split(".")[-1] == EMBEDDING_BASE_CLASS for b in node.bases
            ):
                sites.append(Site(rel(path), scope, node.lineno, node.name))
    return sites


def _imports_root(tree: ast.Module, root: str) -> bool:
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and (n.module or "").split(".")[0] == root:
            return True
        if isinstance(n, ast.Import) and any(a.name.split(".")[0] == root for a in n.names):
            return True
    return False


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


# ── tests: the embedding gateway (ADR 0005, "What safety adds") ────────


def _exact(found: set, allowed: set, what: str) -> None:
    extra = sorted(found - allowed)
    missing = sorted(allowed - found)
    assert not extra and not missing, (
        f"Floor 3: {what} differ from ADR 0005.\n"
        f"  new, not in the ADR (amend ADR 0005 with the user, or move it to the worker): {extra}\n"
        f"  in the ADR, no longer found (amend ADR 0005 to drop it): {missing}"
    )


def test_floor3_get_embedding_provider_sites_equal_adr_0005_allowlist():
    """Item 1: get_embedding_provider outside agents/ and pipeline/ is exactly the ADR's list."""
    _exact(
        request_side_get_embedding_provider_sites(),
        GET_EMBEDDING_PROVIDER_CALL_SITES,
        "get_embedding_provider call sites",
    )


def test_floor3_embed_texts_sites_equal_adr_0005_allowlist():
    """Item 2: .embed_texts outside agents/ and pipeline/ is exactly the ADR's list."""
    _exact({s.key() for s in embed_texts_sites()}, EMBED_TEXTS_CALL_SITES, "embed_texts sites")


def test_floor3_startup_embedding_sites_never_embed():
    """Item 3: the startup probe may build and preload the provider, never embed."""
    sites = [s for s in embed_texts_sites() if s.key() in STARTUP_ONLY_EMBEDDING_SITES]
    assert not sites, "Floor 3: a startup-only embedding site calls embed_texts:\n" + "\n".join(
        f"  {s}" for s in sites
    )


def test_floor3_injected_provider_sites_have_only_worker_callers():
    """Item 4: a function that embeds with a handed-in provider is reached only from the worker."""
    from tests.safety._source import APP_ROOT

    for (module, function), callers in INJECTED_PROVIDER_CALLERS.items():
        # A renamed function would have no references and pass vacuously.
        tree = parse(APP_ROOT.parent / module)
        defined = {
            n.name for n in tree.body if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
        }
        assert function in defined, f"Floor 3: pinned {module}:{function} no longer exists"
        found = references_to(module, function)
        unlisted = sorted(found - callers)
        assert not unlisted, (
            f"Floor 3: {module}:{function} embeds with an injected provider, so every "
            f"caller must be listed in ADR 0005 (INJECTED_PROVIDER_CALLERS).\n"
            f"  unlisted: {unlisted}\n  listed:   {sorted(callers)}"
        )
        for caller in callers:
            assert caller[0].startswith(PIPELINE) or caller in INJECTED_PROVIDER_CALLERS, (
                f"Floor 3: {caller} may call {function} but is neither worker-side nor "
                "itself pinned, so the chain need not end in the worker"
            )
    # Today's wiring: the worker reaches the embedder through the pinned chain.
    assert ("app/pipeline/index.py", "_index") in set().union(
        *(references_to(m, f) for m, f in INJECTED_PROVIDER_CALLERS)
    )


def test_floor3_pipeline_get_embedding_provider_only_in_celery_task_modules():
    """Item 5: every pipeline get_embedding_provider is in a module that registers a task."""
    sites = pipeline_get_embedding_provider_outside_task_modules()
    assert not sites, (
        "Floor 3: get_embedding_provider under app/pipeline/ in a module with no Celery task:\n"
        + "\n".join(f"  {s}" for s in sites)
    )


def test_floor3_no_embedding_backend_reference_outside_agents():
    """Item 6 (§4): no backend class, no test seam, no subclass outside app/agents/**.

    ``sentence_transformers`` joins the SDK ban in
    ``test_floor3_no_provider_sdk_import_outside_agents`` via ``PROVIDER_SDKS``.
    """
    sites = (
        name_references(EMBEDDING_PROVIDER_CLASSES)
        + name_references(EMBEDDING_TEST_SEAMS)
        + embedding_provider_subclasses()
    )
    assert not sites, (
        "Floor 3: embedding backend reached around get_embedding_provider outside "
        "app/agents/**:\n" + "\n".join(f"  {s}" for s in sites)
    )


def test_floor3_embedding_detectors_are_not_vacuous():
    """Item 7: the embedding collectors find what is known to be there."""
    from tests.safety._source import APP_ROOT

    assert ("app/pipeline/index.py", "_index") in {
        s.key() for s in get_embedding_provider_sites(under=PIPELINE)
    }
    embeddings = parse(APP_ROOT / "agents" / "embeddings.py")
    for root in ("openai", "sentence_transformers", "ollama"):
        assert root in PROVIDER_SDKS
        assert _imports_root(embeddings, root), f"no {root} import found in agents/embeddings.py"
    inside = {s.module for s in name_references(EMBEDDING_PROVIDER_CLASSES, exclude=())}
    assert "app/agents/embeddings.py" in inside
    # The banned names are the real ones: a rename would leave the ban guarding nothing.
    defined = {
        n.name for n in ast.walk(embeddings) if isinstance(n, ast.FunctionDef | ast.ClassDef)
    }
    assert EMBEDDING_TEST_SEAMS | EMBEDDING_PROVIDER_CLASSES | {EMBEDDING_BASE_CLASS} <= defined
    assert "get_embedding_provider" in defined
    assert "embed_texts" in defined
    assert ("app/api/qa.py", "ask_question") in {s.key() for s in embed_texts_sites()}
    # aembed_texts is seen: the index service's async embed reaches it by name.
    assert "aembed_texts" in {
        n.name for n in ast.walk(embeddings) if isinstance(n, ast.AsyncFunctionDef)
    }
    assert ("app/services/index_service.py", "aembed_artifact_chunks") in {
        s.key() for s in embed_texts_sites()
    }

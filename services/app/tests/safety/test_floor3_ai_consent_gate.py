"""Floor 3 (spend) guard: AI-processing consent precedes every AI spend (GL#38, SEC-08).

M33-S1-SAFETY-033. Lecture content leaves the instance when an AI provider is
called, so a caller who has not agreed to the current disclosure must be
refused *before* anything spends AI or enqueues AI pipeline work for them.

The route set is **derived from code**, not listed: every live route whose
handler reaches (directly, or through a function in ``app/api``,
``app/services`` or ``app/core``) a call to one of :data:`SINKS` must carry
``require_ai_consent`` in its dependency tree. The backend's own list
(``tests/unit/api/test_ai_consent_gate.py::GATED_ROUTES``) only proves the
routes someone remembered; this one catches the route nobody has written yet.

Pins:

* every derived route depends on ``require_ai_consent`` (structural);
* an unconsented caller gets ``403 ai_consent_required`` on each of them and
  no sink is reached (behavioural; the dependency runs before the handler);
* ``consent_required`` has exactly one bypass, ``settings.single_user_mode``;
  role, tier and ``self_hosted`` do not exempt anyone.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import sys
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests._routes import api_routes
from tests.safety._source import APP_ROOT, SERVICE_ROOT, dotted, parse, rel

#: A call whose final name is one of these spends AI or enqueues AI work.
SINKS = frozenset(
    {"check_ai_quota", "get_agent", "resume_pipeline", "run_pipeline", "apply_async", "delay"}
)

#: Only functions under these packages are followed when resolving a call.
FOLLOWED = ("app/api/", "app/services/", "app/core/")

#: (METHOD, path) -> why a route that reaches a sink needs no consent. Empty:
#: every route that reaches a sink today is an AI route. An entry here is a
#: floor decision and needs a reason a reviewer can check.
CONSENT_EXEMPT: dict[tuple[str, str], str] = {}

#: The backend's GATED_ROUTES at GL#38. The derivation must find at least these,
#: so a resolver regression cannot make the structural check pass vacuously.
KNOWN_GATED = frozenset(
    {
        ("POST", "/api/settings/test-ai"),
        ("POST", "/api/chat/sessions/{session_id}/messages"),
        ("POST", "/api/chat/sessions/{session_id}/messages/stream"),
        ("POST", "/api/qa/ask"),
        ("POST", "/api/concepts/extract/{artifact_id}"),
        ("POST", "/api/uploads"),
        ("POST", "/api/uploads/batch"),
        ("POST", "/api/uploads/capture"),
        ("POST", "/api/uploads/{artifact_id}/retry"),
        ("POST", "/api/artifacts/{artifact_id}/reclassify"),
        ("POST", "/api/review-items/{review_id}/resolve"),
        ("POST", "/api/courses/{course_code}/merge"),
        ("POST", "/api/courseops/documents"),
        # ADR 0007 (GL#45): reaches .delay() and check_ai_quota (SAFETY-024, M33-S2).
        ("POST", "/api/weak-spots/targeted"),
    }
)


# ── call resolution ────────────────────────────────────────────────────


class _Module:
    """One parsed module: its top-level defs and what its imported names point to."""

    def __init__(self, path) -> None:
        self.path = path
        self.tree = parse(path)
        self.defs: dict[str, ast.AST] = {}
        for node in self.tree.body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                self.defs[node.name] = node
            elif isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                        self.defs[f"{node.name}.{item.name}"] = item
        #: local name -> (module dotted path, function name or None for a module)
        self.imports: dict[str, tuple[str, str | None]] = {}
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app"):
                for alias in node.names:
                    local = alias.asname or alias.name
                    sub = f"{node.module}.{alias.name}"
                    if _module_path(sub) is not None:
                        self.imports[local] = (sub, None)
                    else:
                        self.imports[local] = (node.module, alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("app") and alias.asname:
                        self.imports[alias.asname] = (alias.name, None)


def _module_path(dotted_name: str):
    base = SERVICE_ROOT.joinpath(*dotted_name.split("."))
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


_MODULES: dict[str, _Module] = {}


def _module(dotted_name: str) -> _Module | None:
    path = _module_path(dotted_name)
    if path is None or not any(rel(path).startswith(p) for p in FOLLOWED):
        return None
    if dotted_name not in _MODULES:
        _MODULES[dotted_name] = _Module(path)
    return _MODULES[dotted_name]


def _targets(call: ast.Call, mod: _Module, mod_name: str) -> list[tuple[str, str]]:
    """``(module, function)`` pairs a call may land on, among followed modules."""
    func = call.func
    if isinstance(func, ast.Name):
        if func.id in mod.defs:
            return [(mod_name, func.id)]
        if func.id in mod.imports:
            target_mod, fn = mod.imports[func.id]
            if fn is not None:
                return [(target_mod, fn)]
        return []
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        owner = func.value.id
        if owner in mod.imports:
            target_mod, fn = mod.imports[owner]
            if fn is None:
                return [(target_mod, func.attr)]
            return [(target_mod, f"{fn}.{func.attr}")]
    return []


def sink_path(mod_name: str, fn_name: str, seen: set | None = None) -> list[str] | None:
    """A call chain from ``mod_name.fn_name`` to a sink, or None if none is reachable."""
    seen = set() if seen is None else seen
    if (mod_name, fn_name) in seen:
        return None
    seen.add((mod_name, fn_name))
    mod = _module(mod_name)
    if mod is None or fn_name not in mod.defs:
        return None
    for node in ast.walk(mod.defs[fn_name]):
        if not isinstance(node, ast.Call):
            continue
        name = dotted(node.func).rsplit(".", 1)[-1] or getattr(node.func, "attr", "")
        if name in SINKS:
            return [f"{mod_name}.{fn_name}", f"{name}() @ line {node.lineno}"]
        for target in _targets(node, mod, mod_name):
            chain = sink_path(*target, seen)
            if chain is not None:
                return [f"{mod_name}.{fn_name}", *chain]
    return None


# ── live routes ────────────────────────────────────────────────────────


def _api_routes():

    from app.main import app

    return api_routes(app)


def _handler(route) -> tuple[str, str]:
    endpoint = inspect.unwrap(route.endpoint)
    return endpoint.__module__, endpoint.__qualname__


def _dependency_calls(route) -> set:
    found: set = set()

    def walk(dependant) -> None:
        for dep in dependant.dependencies:
            found.add(dep.call)
            walk(dep)

    walk(route.dependant)
    return found


def derived_gated_routes() -> dict[tuple[str, str], list[str]]:
    """(METHOD, path) -> the call chain that makes it an AI route."""
    out: dict[tuple[str, str], list[str]] = {}
    for route in _api_routes():
        chain = sink_path(*_handler(route))
        if chain is None:
            continue
        for method in route.methods:
            out[(method, route.path)] = chain
    return out


def test_floor3_consent_route_derivation_is_not_vacuous():
    """The resolver finds at least every route the backend gated by hand."""
    derived = derived_gated_routes()
    missing = sorted(KNOWN_GATED - set(derived))
    assert not missing, (
        "the sink resolver no longer reaches these known AI routes; fix the resolver "
        f"before trusting the consent sweep: {missing}"
    )


def test_floor3_every_ai_route_requires_consent():
    """Every route that reaches an AI sink carries ``require_ai_consent``."""
    from app.api.deps import require_ai_consent

    routes = {(m, r.path): r for r in _api_routes() for m in r.methods}
    offenders = []
    for key, chain in sorted(derived_gated_routes().items()):
        if key in CONSENT_EXEMPT:
            continue
        if require_ai_consent not in _dependency_calls(routes[key]):
            offenders.append(f"{key[0]} {key[1]}: {' -> '.join(chain)}")
    assert not offenders, (
        "routes that spend AI or enqueue AI work without the consent gate "
        "(add dependencies=[Depends(require_ai_consent)]):\n" + "\n".join(offenders)
    )


def test_floor3_consent_exemptions_are_live():
    """A stale exemption is a hole waiting for a route to fill it."""
    derived = derived_gated_routes()
    stale = sorted(k for k in CONSENT_EXEMPT if k not in derived)
    assert not stale, f"CONSENT_EXEMPT entries no longer reach a sink: {stale}"


def test_floor3_consent_resolver_follows_imports_and_helpers(tmp_path, monkeypatch):
    """Direct, same-module helper, imported function and module-alias calls all resolve."""
    import tests.safety.test_floor3_ai_consent_gate as me

    pkg = tmp_path / "app"
    (pkg / "api").mkdir(parents=True)
    (pkg / "services").mkdir()
    for p in (pkg, pkg / "api", pkg / "services"):
        (p / "__init__.py").write_text("")
    (pkg / "services" / "svc.py").write_text(
        "def deep():\n    return task.delay(1)\n\ndef clean():\n    return 1\n"
    )
    (pkg / "api" / "r.py").write_text(
        "from app.services import svc\n"
        "from app.services.svc import deep\n"
        "def helper():\n    return run_pipeline('x')\n"
        "def via_helper():\n    return helper()\n"
        "def via_alias():\n    return svc.deep()\n"
        "def via_name():\n    return deep()\n"
        "def none():\n    return svc.clean()\n"
        "def direct():\n    return get_agent()\n"
    )
    monkeypatch.setattr(me, "SERVICE_ROOT", tmp_path)
    monkeypatch.setattr(me, "_MODULES", {})
    monkeypatch.setattr(me, "rel", lambda p: p.resolve().relative_to(tmp_path).as_posix())
    for fn in ("via_helper", "via_alias", "via_name", "direct"):
        assert me.sink_path("app.api.r", fn) is not None, fn
    assert me.sink_path("app.api.r", "none") is None


def test_floor3_consent_structural_check_is_red_without_the_dependency():
    """Mutation: a derived route whose dependency tree lacks the gate is reported."""
    from app.api.deps import require_ai_consent

    route = next(r for r in _api_routes() if r.path == "/api/qa/ask")
    assert require_ai_consent in _dependency_calls(route)
    stripped = SimpleNamespace(
        dependant=SimpleNamespace(
            dependencies=[
                d for d in route.dependant.dependencies if d.call is not require_ai_consent
            ]
        )
    )
    assert require_ai_consent not in _dependency_calls(stripped)


# ── behaviour: the 403 comes first ─────────────────────────────────────


def _fill(path: str) -> str:
    out, i = [], 0
    while i < len(path):
        if path[i] == "{":
            j = path.index("}", i)
            out.append("floor3-consent-probe")
            i = j + 1
        else:
            out.append(path[i])
            i += 1
    return "".join(out)


@pytest.fixture
def sink_mocks():
    """Replace every sink the API layer can reach with a recording mock."""
    from celery.app.task import Task

    importlib.import_module("app.main")
    mocks: dict[str, MagicMock] = {}
    patchers = []

    def add(target, attr, mock):
        p = patch.object(target, attr, mock)
        p.start()
        patchers.append(p)
        mocks[f"{getattr(target, '__name__', target)}.{attr}"] = mock

    for name, module in list(sys.modules.items()):
        if not name.startswith("app.") or module is None:
            continue
        for attr in ("get_agent", "run_pipeline", "resume_pipeline", "check_ai_quota"):
            if callable(getattr(module, attr, None)) and attr in vars(module):
                add(module, attr, AsyncMock() if attr == "check_ai_quota" else MagicMock())
    add(Task, "apply_async", MagicMock())
    add(Task, "delay", MagicMock())
    try:
        yield mocks
    finally:
        for p in reversed(patchers):
            p.stop()


@pytest.mark.asyncio
async def test_floor3_unconsented_caller_is_refused_before_any_sink(
    async_client, default_test_user, sink_mocks
):
    """Each derived route: 403 ``ai_consent_required``, and no sink was reached."""
    from app.config import settings

    default_test_user.ai_processing_consent_at = None
    default_test_user.ai_processing_consent_version = None
    failures = []
    with patch.object(settings, "single_user_mode", False):
        for (method, path), _chain in sorted(derived_gated_routes().items()):
            if (method, path) in CONSENT_EXEMPT:
                continue
            resp = await async_client.request(method, _fill(path))
            body = (
                resp.json()
                if resp.headers.get("content-type", "").startswith("application/json")
                else {}
            )
            if resp.status_code != 403 or body.get("code") != "ai_consent_required":
                failures.append(f"{method} {path}: {resp.status_code} {body}")
    called = {k: m.call_count for k, m in sink_mocks.items() if m.called}
    assert not failures, "AI routes that did not refuse an unconsented caller:\n" + "\n".join(
        failures
    )
    assert not called, f"a sink ran for an unconsented caller: {called}"


@pytest.mark.asyncio
async def test_floor3_outdated_consent_version_is_refused(async_client, default_test_user):
    """A consent to older disclosure wording is no consent."""
    from app.config import settings

    default_test_user.ai_processing_consent_at = datetime.now(UTC)
    default_test_user.ai_processing_consent_version = 1
    with (
        patch.object(settings, "single_user_mode", False),
        patch.object(settings, "ai_consent_version", 2),
    ):
        resp = await async_client.post("/api/qa/ask", json={"question": "q"})
    assert resp.status_code == 403
    assert resp.json()["code"] == "ai_consent_required"


# ── the only bypass ────────────────────────────────────────────────────


@pytest.mark.parametrize("role", ["user", "admin", "demo"])
@pytest.mark.parametrize("tier", ["free", "pro"])
@pytest.mark.parametrize("self_hosted", [False, True])
def test_floor3_consent_has_no_role_tier_or_self_hosted_bypass(role, tier, self_hosted):
    """Outside single-user mode, nobody without a current consent passes."""
    from app.config import settings
    from app.services import consent_service

    unconsented = SimpleNamespace(
        role=role, tier=tier, ai_processing_consent_at=None, ai_processing_consent_version=None
    )
    no_version = SimpleNamespace(
        role=role,
        tier=tier,
        ai_processing_consent_at=datetime.now(UTC),
        ai_processing_consent_version=None,
    )
    with (
        patch.object(settings, "single_user_mode", False),
        patch.object(settings, "self_hosted", self_hosted),
        patch.object(settings, "ai_consent_version", 1),
    ):
        assert consent_service.consent_required(unconsented) is True
        assert consent_service.consent_required(no_version) is True


def test_floor3_single_user_mode_is_the_only_consent_bypass():
    """Every falsy return in ``consent_required`` sits under ``settings.single_user_mode``."""
    from app.services import consent_service

    tree = ast.parse(inspect.getsource(consent_service.consent_required))
    fn = tree.body[0]
    early = []
    for stmt in fn.body:
        if isinstance(stmt, ast.If):
            early.append(stmt)
    assert len(early) == 1, "consent_required gained a second early branch; review it"
    (branch,) = early
    assert dotted(branch.test) == "settings.single_user_mode", ast.unparse(branch.test)
    assert not branch.orelse

    # And the dependency itself adds no branch of its own.
    from app.api import deps

    dep = ast.parse(inspect.getsource(deps.require_ai_consent)).body[0]
    assert not any(isinstance(n, ast.If | ast.Try | ast.IfExp) for n in ast.walk(dep))


def test_floor3_consent_error_is_not_swallowed_in_app():
    """Nothing in app/ catches the consent error (or its base) without re-raising it."""
    offenders = []
    for path in sorted(APP_ROOT.rglob("*.py")):
        for node in ast.walk(parse(path)):
            if isinstance(node, ast.ExceptHandler) and node.type is not None:
                names = {dotted(n).rsplit(".", 1)[-1] for n in ast.walk(node.type)}
                if not names & {"AiConsentRequiredError", "AuthorizationError"}:
                    continue
                # The login throttle catches AuthorizationError to count a
                # failure and re-raises it; only a handler that can fall
                # through without re-raising could convert the 403 into a pass.
                reraises = any(isinstance(s, ast.Raise) and s.exc is None for s in ast.walk(node))
                if not reraises:
                    offenders.append(f"{rel(path)}:{node.lineno}")
    assert not offenders, f"consent error caught (could turn the 403 into a pass): {offenders}"

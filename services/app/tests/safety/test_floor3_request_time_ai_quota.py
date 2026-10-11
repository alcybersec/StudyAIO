"""Request-time AI spend on the instance provider is quota-checked and metered as the caller.

M32 gate condition G1 (``docs/gates/M32/floors.md`` N-1), pinned in
M33-S1-SAFETY-005 after backend ``421dfa9``. Until then ``POST /api/settings/test-ai``
built ``get_agent(None)`` (the operator's provider) with no ``check_ai_quota``, so
no per-user quota, no global ceiling, no metering and no rate limit.

This rides floor 3's ADR 0003 list: every request-time ``get_agent`` call site is
reached from a route handler, and that handler must

1. check the quota for the *caller* (``check_ai_quota(session, <caller>.id, …)``,
   floor-1 wiring) before the spend, unconditionally or behind exactly
   "this caller's agent config is None" (the instance provider; an own-credential
   call costs the operator nothing), and never inside a ``try``, loop or closure
   that could swallow or skip the refusal; and
2. record the call against the same caller (``record_ai_call(session, <caller>.id)``,
   in the handler or in the site function on a ``user_id`` the handler fills with
   ``<caller>.id``).

A new ADR 0003 site fails ``test_…_every_adr_0003_site_has_a_pinned_route`` until it
is given a route here, so a site cannot join the allowlist unmetered.

The static checks need no services. The direct test for test-ai goes through the
real app with the quota service mocked, so it pins the *values* passed, not just
their shape.
"""

from __future__ import annotations

import ast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.safety._source import SERVICE_ROOT, app_modules, dotted, parse, rel
from tests.safety.test_floor3_ai_via_adapter import REQUEST_TIME_GET_AGENT_CALL_SITES

#: ADR 0003 site -> the route handlers that reach it within a request. The service
#: sites' callers are re-derived and compared in both directions.
SPEND_ROUTES: dict[tuple[str, str], set[tuple[str, str]]] = {
    ("app/api/qa.py", "ask_question"): {("app/api/qa.py", "ask_question")},
    ("app/api/settings.py", "test_ai_connection"): {("app/api/settings.py", "test_ai_connection")},
    ("app/services/chat_service.py", "send_message"): {("app/api/chat.py", "send_message")},
    ("app/services/chat_service.py", "stream_message"): {("app/api/chat.py", "stream_message")},
    ("app/services/concept_service.py", "extract_and_save_concepts"): {
        ("app/api/concepts.py", "extract_concepts")
    },
}

CALLER_DEPENDENCIES = frozenset({"get_current_user", "get_current_user_or_default"})
CONFIG_LOADERS = frozenset({"get_user_agent_config", "get_user_ai_context"})


# ── analysis ───────────────────────────────────────────────────────────


def _function(tree: ast.Module, name: str) -> ast.AsyncFunctionDef | ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == name:
            return node
    raise LookupError(name)


def _parents(fn: ast.AST) -> dict[int, ast.AST]:
    out: dict[int, ast.AST] = {}
    for node in ast.walk(fn):
        for child in ast.iter_child_nodes(node):
            out[id(child)] = node
    return out


def _calls(fn: ast.AST, suffix: str) -> list[ast.Call]:
    return [
        n
        for n in ast.walk(fn)
        if isinstance(n, ast.Call)
        and (dotted(n.func) == suffix or dotted(n.func).endswith(f".{suffix}"))
    ]


def caller_param(fn: ast.AsyncFunctionDef | ast.FunctionDef) -> str | None:
    """The parameter bound to ``Depends(get_current_user[_or_default])``."""
    args = [*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs]
    defaults = [None] * (
        len(fn.args.posonlyargs) + len(fn.args.args) - len(fn.args.defaults)
    ) + list(fn.args.defaults)
    defaults += list(fn.args.kw_defaults)
    found = [
        a.arg
        for a, d in zip(args, defaults, strict=True)
        if isinstance(d, ast.Call)
        and dotted(d.func) == "Depends"
        and d.args
        and dotted(d.args[0]) in CALLER_DEPENDENCIES
    ]
    return found[0] if len(found) == 1 else None


def _user_arg(call: ast.Call) -> ast.AST | None:
    for kw in call.keywords:
        if kw.arg == "user_id":
            return kw.value
    return call.args[1] if len(call.args) > 1 else None


def _is_caller_id(node: ast.AST | None, caller: str) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "id"
        and isinstance(node.value, ast.Name)
        and node.value.id == caller
    )


def _instance_config_names(fn: ast.AST, caller: str) -> set[str]:
    """Names passed as ``user_settings`` to ``get_agent`` and loaded for the caller."""
    passed: set[str] = set()
    for call in _calls(fn, "get_agent"):
        arg = next((k.value for k in call.keywords if k.arg == "user_settings"), None)
        if arg is None and call.args:
            arg = call.args[0]
        if isinstance(arg, ast.Name):
            passed.add(arg.id)
    loaded: set[str] = set()
    for node in ast.walk(fn):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        value = node.value.value if isinstance(node.value, ast.Await) else node.value
        if not (
            isinstance(value, ast.Call)
            and dotted(value.func).split(".")[-1] in CONFIG_LOADERS
            and any(
                _is_caller_id(a, caller) for a in [*value.args, *(k.value for k in value.keywords)]
            )
        ):
            continue
        target = node.targets[0]
        if isinstance(target, ast.Tuple) and target.elts:
            target = target.elts[0]
        if isinstance(target, ast.Name):
            loaded.add(target.id)
    return passed & loaded


def _is_none_test(node: ast.AST, names: set[str]) -> bool:
    return (
        isinstance(node, ast.Compare)
        and isinstance(node.left, ast.Name)
        and node.left.id in names
        and len(node.ops) == 1
        and isinstance(node.ops[0], ast.Is)
        and isinstance(node.comparators[0], ast.Constant)
        and node.comparators[0].value is None
    )


def _instance_guard(test: ast.AST, fn: ast.AST, configs: set[str]) -> bool:
    """``cfg is None``, or a local assigned exactly once from ``cfg is None``."""
    if _is_none_test(test, configs):
        return True
    if not isinstance(test, ast.Name):
        return False
    assigns = [
        n
        for n in ast.walk(fn)
        if isinstance(n, ast.Assign | ast.AugAssign | ast.AnnAssign | ast.NamedExpr)
        and any(
            isinstance(t, ast.Name) and t.id == test.id
            for t in (n.targets if isinstance(n, ast.Assign) else [n.target])
        )
    ]
    return (
        len(assigns) == 1
        and isinstance(assigns[0], ast.Assign)
        and _is_none_test(assigns[0].value, configs)
    )


def _unconditional_or_instance_only(
    call: ast.Call, fn: ast.AST, parents: dict[int, ast.AST], configs: set[str]
) -> bool:
    """The check runs on every instance-provider request: no try, loop or closure around it."""
    child: ast.AST = call
    node = parents.get(id(call))
    while node is not None and node is not fn:
        if isinstance(node, ast.If):
            if child not in node.body or not _instance_guard(node.test, fn, configs):
                return False
        elif not isinstance(node, ast.Await | ast.Expr):
            return False
        child, node = node, parents.get(id(node))
    return node is fn


def spend_lineno(fn: ast.AST, site: tuple[str, str]) -> int | None:
    """First line where ``fn`` reaches the AI: ``get_agent`` itself, or the site function."""
    name = "get_agent" if site[0].startswith("app/api/") else site[1]
    lines = [c.lineno for c in _calls(fn, name)]
    return min(lines) if lines else None


def quota_problems(source: str, handler: str, site: tuple[str, str]) -> list[str]:
    """Why ``handler`` does not check the caller's quota before reaching ``site``."""
    fn = _function(ast.parse(source), handler)
    caller = caller_param(fn)
    if caller is None:
        return ["no single Depends(get_current_user*) caller parameter"]
    spend = spend_lineno(fn, site)
    if spend is None:
        return [f"does not reach {site[1]}"]
    parents = _parents(fn)
    configs = _instance_config_names(fn, caller)
    good = [
        c
        for c in _calls(fn, "check_ai_quota")
        if _is_caller_id(_user_arg(c), caller)
        and c.lineno < spend
        and _unconditional_or_instance_only(c, fn, parents, configs)
    ]
    if good:
        return []
    return [
        f"no check_ai_quota(session, {caller}.id, …) before line {spend}, "
        "unconditional or behind '<caller config> is None' only"
    ]


def _records_for(fn: ast.AST, user: ast.AST | None) -> bool:
    return (
        any(
            _user_arg(c) is not None and ast.dump(_user_arg(c)) == ast.dump(user)
            for c in _calls(fn, "record_ai_call")
        )
        if user is not None
        else False
    )


def metering_problems(
    handler_source: str, handler: str, site: tuple[str, str], site_source: str | None
) -> list[str]:
    """Why the call is not recorded against the caller."""
    fn = _function(ast.parse(handler_source), handler)
    caller = caller_param(fn)
    if caller is None:
        return ["no single Depends(get_current_user*) caller parameter"]
    caller_id = ast.Attribute(value=ast.Name(id=caller, ctx=ast.Load()), attr="id", ctx=ast.Load())
    if _records_for(fn, caller_id):
        return []
    if site_source is not None:
        site_fn = _function(ast.parse(site_source), site[1])
        passes_caller = [
            c
            for c in _calls(fn, site[1])
            if any(k.arg == "user_id" and _is_caller_id(k.value, caller) for k in c.keywords)
        ]
        if passes_caller and _records_for(site_fn, ast.Name(id="user_id", ctx=ast.Load())):
            return []
    return [f"no record_ai_call(session, {caller}.id) in the handler or the site on its behalf"]


def _module_aliases(tree: ast.Module, module: str, function: str) -> tuple[set[str], set[str]]:
    """Local names for ``module`` and for ``module.function`` in one file."""
    dotted_mod = module.removesuffix(".py").replace("/", ".")
    package, _, leaf = dotted_mod.rpartition(".")
    mods: set[str] = set()
    funcs: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == package:
            mods |= {a.asname or a.name for a in node.names if a.name == leaf}
        elif isinstance(node, ast.ImportFrom) and node.module == dotted_mod:
            funcs |= {a.asname or a.name for a in node.names if a.name == function}
        elif isinstance(node, ast.Import):
            mods |= {a.asname for a in node.names if a.name == dotted_mod and a.asname}
    return mods, funcs


def request_callers(site: tuple[str, str]) -> set[tuple[str, str]]:
    """Top-level functions outside the site's module and the worker that reference it."""
    module, function = site
    out: set[tuple[str, str]] = set()
    for path in app_modules(exclude=(module, "app/pipeline/", "app/agents/")):
        tree = parse(path)
        mods, funcs = _module_aliases(tree, module, function)
        if not mods and not funcs:
            continue
        for top in tree.body:
            if not isinstance(top, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for n in ast.walk(top):
                if (
                    isinstance(n, ast.Attribute)
                    and n.attr == function
                    and isinstance(n.value, ast.Name)
                    and n.value.id in mods
                ) or (isinstance(n, ast.Name) and n.id in funcs):
                    out.add((rel(path), top.name))
    return out


def _source(module: str) -> str:
    return (SERVICE_ROOT / module).read_text(encoding="utf-8")


def _routes() -> list[tuple[tuple[str, str], tuple[str, str]]]:
    return sorted((site, route) for site, routes in SPEND_ROUTES.items() for route in routes)


# ── the pin ────────────────────────────────────────────────────────────


def test_floor3_every_adr_0003_site_has_a_pinned_route() -> None:
    """A site added to ADR 0003 must be metered here before it is green."""
    assert set(SPEND_ROUTES) == REQUEST_TIME_GET_AGENT_CALL_SITES


@pytest.mark.parametrize(
    "site", sorted(s for s in SPEND_ROUTES if not s[0].startswith("app/api/")), ids=str
)
def test_floor3_service_site_routes_are_exactly_the_pinned_ones(site) -> None:
    """A second request-time caller of a service site would be unchecked."""
    assert request_callers(site) == SPEND_ROUTES[site]


@pytest.mark.parametrize(("site", "route"), _routes(), ids=lambda v: f"{v[0]}:{v[1]}")
def test_floor3_instance_ai_spend_is_quota_checked_for_the_caller(site, route) -> None:
    assert quota_problems(_source(route[0]), route[1], site) == []


@pytest.mark.parametrize(("site", "route"), _routes(), ids=lambda v: f"{v[0]}:{v[1]}")
def test_floor3_instance_ai_spend_is_recorded_against_the_caller(site, route) -> None:
    site_source = None if site == route else _source(site[0])
    assert metering_problems(_source(route[0]), route[1], site, site_source) == []


# ── the detector, on synthetic source ──────────────────────────────────

_HEAD = """
async def h(session=Depends(get_session), user: User = Depends(get_current_user_or_default)):
"""
_SITE = ("app/api/x.py", "h")


def _h(body: str) -> str:
    return _HEAD + "".join(f"    {line}\n" for line in body.strip("\n").splitlines())


GOOD_UNCONDITIONAL = _h("""
await quota_service.check_ai_quota(session, user.id, user.tier)
agent = get_agent(user_settings=None)
await billing_service.record_ai_call(session, user.id, agent=agent)
""")

GOOD_INSTANCE_ONLY = _h("""
cfg = await get_user_agent_config(session, user.id)
metered = cfg is None
if metered:
    await quota_service.check_ai_quota(session, user.id, user.tier)
agent = get_agent(user_settings=cfg)
""")


@pytest.mark.parametrize("source", [GOOD_UNCONDITIONAL, GOOD_INSTANCE_ONLY])
def test_floor3_quota_detector_accepts_a_checked_handler(source) -> None:
    assert quota_problems(source, "h", _SITE) == []


@pytest.mark.parametrize(
    "body",
    [
        pytest.param("agent = get_agent(user_settings=None)", id="no-check"),
        pytest.param(
            "await check_ai_quota(session, other.id, 'pro')\nagent = get_agent(None)",
            id="other-user",
        ),
        pytest.param(
            "await check_ai_quota(session, user_id='x')\nagent = get_agent(None)",
            id="literal-user",
        ),
        pytest.param(
            "agent = get_agent(None)\nawait check_ai_quota(session, user.id, user.tier)",
            id="after-spend",
        ),
        pytest.param(
            "try:\n    await check_ai_quota(session, user.id, user.tier)\n"
            "except Exception:\n    pass\nagent = get_agent(None)",
            id="swallowed",
        ),
        pytest.param(
            "if user.tier == 'free':\n    await check_ai_quota(session, user.id, user.tier)\n"
            "agent = get_agent(None)",
            id="unrelated-guard",
        ),
        pytest.param(
            "cfg = await get_user_agent_config(session, user.id)\nif cfg is not None:\n"
            "    await check_ai_quota(session, user.id, user.tier)\nagent = get_agent(cfg)",
            id="inverted-guard",
        ),
        pytest.param(
            "cfg = await get_user_agent_config(session, user.id)\nm = cfg is None\nm = True\n"
            "if m:\n    await check_ai_quota(session, user.id, user.tier)\nagent = get_agent(cfg)",
            id="reassigned-guard",
        ),
        pytest.param(
            "cfg = await get_user_agent_config(session, user.id)\nif cfg is None:\n"
            "    pass\nelse:\n    await check_ai_quota(session, user.id, user.tier)\n"
            "agent = get_agent(cfg)",
            id="else-branch",
        ),
        pytest.param(
            "cfg = {}\nif cfg is None:\n    await check_ai_quota(session, user.id, user.tier)\n"
            "agent = get_agent(cfg)",
            id="config-not-the-callers",
        ),
        pytest.param("await check_ai_quota(session, user.id, user.tier)", id="no-spend"),
    ],
)
def test_floor3_quota_detector_rejects_an_unchecked_handler(body) -> None:
    assert quota_problems(_h(body), "h", _SITE)


def test_floor3_quota_detector_needs_a_caller_parameter() -> None:
    source = "async def h(session, user):\n    agent = get_agent(None)\n"
    assert quota_problems(source, "h", _SITE)
    assert metering_problems(source, "h", _SITE, None)


@pytest.mark.parametrize(
    ("body", "site_body", "ok"),
    [
        pytest.param("await record_ai_call(session, user.id)", None, True, id="handler"),
        pytest.param("await record_ai_call(session, other.id)", None, False, id="other-user"),
        pytest.param("pass", None, False, id="none"),
        pytest.param(
            "await svc.site(session, user_id=user.id)",
            "await record_ai_call(session, user_id)",
            True,
            id="site-on-callers-behalf",
        ),
        pytest.param(
            "await svc.site(session, user_id=other.id)",
            "await record_ai_call(session, user_id)",
            False,
            id="site-for-another",
        ),
        pytest.param(
            "await svc.site(session, user_id=user.id)",
            "await record_ai_call(session, owner_id)",
            False,
            id="site-records-someone-else",
        ),
    ],
)
def test_floor3_metering_detector(body, site_body, ok) -> None:
    site = ("app/services/svc.py", "site")
    site_source = (
        None if site_body is None else f"async def site(session, user_id):\n    {site_body}\n"
    )
    problems = metering_problems(_h(body), "h", site, site_source)
    assert (problems == []) is ok


def test_floor3_route_derivation_is_not_vacuous() -> None:
    """The real chat route is found through ``from app.services import chat_service``."""
    assert ("app/api/chat.py", "send_message") in request_callers(
        ("app/services/chat_service.py", "send_message")
    )
    tree = ast.parse("import app.services.svc as s\nfrom app.services.svc import site as f\n")
    assert _module_aliases(tree, "app/services/svc.py", "site") == ({"s"}, {"f"})


# ── test-ai, through the app ───────────────────────────────────────────

URL = "/api/settings/test-ai"
CONFIG = "app.services.settings_service.get_user_agent_config"
GET_AGENT = "app.agents.factory.get_agent"
CHECK = "app.services.quota_service.check_ai_quota"
RECORD = "app.services.billing_service.record_ai_call"


@pytest.fixture
async def caller_client(async_client, make_user):
    """``async_client`` acting as a non-default, free-tier user."""
    from app.api.deps import get_current_user_or_default
    from app.main import app

    caller = make_user(id="00000000-0000-0000-0000-0000000000b0", tier="free")

    async def override():
        return caller

    previous = app.dependency_overrides.get(get_current_user_or_default)
    app.dependency_overrides[get_current_user_or_default] = override
    try:
        yield async_client, caller
    finally:
        if previous is not None:
            app.dependency_overrides[get_current_user_or_default] = previous


def _agent(fail: bool) -> MagicMock:
    agent = MagicMock()
    agent.classify_lecture = AsyncMock(
        side_effect=RuntimeError("provider down") if fail else None,
        return_value=MagicMock(confidence=0.5),
    )
    return agent


@pytest.mark.parametrize("fail", [False, True], ids=["ok", "provider-error"])
async def test_floor3_test_ai_on_instance_checks_then_meters_the_caller(caller_client, fail):
    client, caller = caller_client
    order: list[str] = []
    agent = _agent(fail)

    def build(**_kw):
        order.append("get_agent")
        return agent

    check = AsyncMock(side_effect=lambda *a, **k: order.append("check"))
    record = AsyncMock(side_effect=lambda *a, **k: order.append("record"))
    with (
        patch(CONFIG, AsyncMock(return_value=None)),
        patch(GET_AGENT, side_effect=build),
        patch(CHECK, check),
        patch(RECORD, record),
    ):
        response = await client.post(URL)

    assert response.status_code == (502 if fail else 200)
    assert order == ["check", "get_agent", "record"]
    assert check.await_args.args[1] == caller.id  # load-bearing: the caller's quota
    assert check.await_args.args[2] == caller.tier
    assert record.await_args.args[1] == caller.id  # load-bearing: billed to the caller


async def test_floor3_test_ai_refused_by_the_ceiling_never_builds_an_agent(caller_client):
    from app.core.exceptions import GlobalCeilingError

    client, _caller = caller_client
    with (
        patch(CONFIG, AsyncMock(return_value=None)),
        patch(GET_AGENT) as get_agent,
        patch(CHECK, AsyncMock(side_effect=GlobalCeilingError("AI call", 100, 60))),
        patch(RECORD, AsyncMock()) as record,
    ):
        response = await client.post(URL)

    assert response.status_code == 429
    get_agent.assert_not_called()
    record.assert_not_awaited()


def test_floor3_own_provider_config_never_builds_the_instance_agent() -> None:
    """Why test-ai may skip metering when the config is not None.

    Every config ``get_user_agent_config`` can return names a provider the user
    chose; with no credential behind it the factory refuses rather than falling
    back to the instance's. If that ever changed, ``metered = cfg is None`` would
    leave an unmetered instance path.
    """
    from app.agents.factory import get_agent
    from app.core.exceptions import ProviderCredentialError
    from app.services.settings_service import (
        STUDYAIO_BACKEND,
        VALID_BACKENDS,
        _agent_config_from_overrides,
    )

    backends = sorted(VALID_BACKENDS - {STUDYAIO_BACKEND})
    assert len(backends) >= 5
    for backend in backends:
        config = _agent_config_from_overrides({"agent_backend": backend})
        assert config is not None, backend
        with pytest.raises(ProviderCredentialError):
            get_agent(user_settings=config)
    assert _agent_config_from_overrides({}) is None
    assert _agent_config_from_overrides({"agent_backend": "bogus"}) is None

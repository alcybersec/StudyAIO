"""Floors 1 and 2: Prometheus metrics carry no identifier, credential or exception text.

M32 gate condition G3. The worker serves ``/metrics`` on ``127.0.0.1:9101``;
the api serves ``/metrics`` on ``:8000``, which is reachable on the private
network (the reverse proxy and nginx do not forward it). Nothing there asks
for a login, so anything in a label is readable by anyone on that network, and a
label is also written to the worker's multiprocess tmpfs files.

The policy, from ``app/pipeline/metrics.py``: labels are low-cardinality enums
only, ``stage``, ``outcome`` and ``error_class``, and ``error_class`` is an
exception's *class name*, never its message. This pins it for every metric under
``app/**``, so a new metric with a ``user_id`` label, or an ``outcome=str(exc)``,
fails here rather than at a scrape. The api side is the Instrumentator's
``handler`` label: the route *template*, never the raw path with its ids.
"""

from __future__ import annotations

import ast

import httpx
import pytest

from tests.safety._source import app_modules, dotted, parse, rel

ALLOWED_LABELS = frozenset({"stage", "outcome", "error_class"})
#: Locals a label value may be read from. Each is bound from a constant table or a
#: literal at every site today; a new name is a review, not a typo fix.
ALLOWED_VALUE_NAMES = frozenset({"stage", "outcome"})
METRIC_TYPES = frozenset({"Counter", "Histogram", "Gauge", "Summary", "Enum", "Info"})
#: Metrics whose ``error_class`` is a local bound from ``<Class>.__name__``, a class
#: defined in the same module, rather than ``type(exc).__name__``. Each is a review:
#: the local must be assigned only from that spelling in the enclosing function.
CLASS_NAME_LOCAL_SITES = {
    ("app/agents/claude_code.py", "CLI_SPAWN_REFUSALS"): (
        "SEC-006 option F (M34-S2): spawn refusals; error_class is "
        "ClaudeCliUnavailableError.__name__, counted before the error is raised"
    ),
}
#: Instrumentator keywords that keep the ``handler`` label a template.
INSTRUMENTATOR_FORBIDDEN = {"should_group_untemplated": False}


def _prometheus_names(tree: ast.Module) -> set[str]:
    """Local names bound to prometheus_client metric classes (not collections.Counter)."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("prometheus_client"):
            names |= {a.asname or a.name for a in node.names if a.name in METRIC_TYPES}
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith("prometheus_client"):
                    names |= {f"{a.asname or a.name}.{t}" for t in METRIC_TYPES}
    return names


def label_name_problems(tree: ast.Module, module: str) -> list[str]:
    """Metric declarations whose label names are not literal and allowed."""
    names = _prometheus_names(tree)
    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and dotted(node.func) in names):
            continue
        labels = next((k.value for k in node.keywords if k.arg == "labelnames"), None)
        if labels is None and len(node.args) > 2:
            labels = node.args[2]
        if labels is None:
            continue
        if not isinstance(labels, ast.List | ast.Tuple) or not all(
            isinstance(e, ast.Constant) and e.value in ALLOWED_LABELS for e in labels.elts
        ):
            out.append(f"{module}:{node.lineno} labels {ast.unparse(labels)}")
    return out


def _allowed_value(key: str | None, value: ast.AST) -> bool:
    if key == "error_class":
        # type(exc).__name__: a class name is fixed by code and cannot carry a message.
        return (
            isinstance(value, ast.Attribute)
            and value.attr == "__name__"
            and isinstance(value.value, ast.Call)
            and dotted(value.value.func) == "type"
            and len(value.value.args) == 1
            and not value.value.keywords
        )
    if isinstance(value, ast.Constant):
        return isinstance(value.value, str)
    return isinstance(value, ast.Name) and value.id in ALLOWED_VALUE_NAMES


def _class_name_local(scope: ast.AST, tree: ast.Module, value: ast.AST) -> bool:
    """``value`` is a local assigned only ``<Class>.__name__`` (a class of this module)."""
    if not isinstance(value, ast.Name):
        return False
    classes = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
    bound = [
        n.value
        for n in ast.walk(scope)
        if isinstance(n, ast.Assign | ast.AnnAssign | ast.AugAssign | ast.NamedExpr)
        and any(
            isinstance(t, ast.Name) and t.id == value.id
            for t in (n.targets if isinstance(n, ast.Assign) else [n.target])
        )
    ]
    return bool(bound) and all(
        isinstance(b, ast.Attribute)
        and b.attr == "__name__"
        and isinstance(b.value, ast.Name)
        and b.value.id in classes
        for b in bound
    )


def _labels_calls(tree: ast.Module):
    """``(enclosing function or module, call)`` for every ``.labels(...)`` call."""
    scopes = [
        tree,
        *(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)),
    ]
    seen: set[int] = set()
    for scope in reversed(scopes):  # innermost first
        for node in ast.walk(scope):
            if (
                id(node) not in seen
                and isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "labels"
            ):
                seen.add(id(node))
                yield scope, node


def label_value_problems(tree: ast.Module, module: str) -> list[str]:
    """``.labels(...)`` calls with a label or value outside the policy."""
    out = []
    for scope, node in _labels_calls(tree):
        metric = dotted(node.func.value)
        reviewed = (module, metric) in CLASS_NAME_LOCAL_SITES

        def ok(k: ast.keyword, scope: ast.AST = scope, reviewed: bool = reviewed) -> bool:
            if k.arg == "error_class" and reviewed and _class_name_local(scope, tree, k.value):
                return True
            return k.arg in ALLOWED_LABELS and _allowed_value(k.arg, k.value)

        bad = bool(node.args) or not all(ok(k) for k in node.keywords)
        if bad:
            out.append(f"{module}:{node.lineno} {ast.unparse(node)[:100]}")
    return out


def instrumentator_problems(tree: ast.Module, module: str) -> list[str]:
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and dotted(node.func).endswith("Instrumentator"):
            for k in node.keywords:
                if (
                    k.arg in INSTRUMENTATOR_FORBIDDEN
                    and isinstance(k.value, ast.Constant)
                    and k.value.value == INSTRUMENTATOR_FORBIDDEN[k.arg]
                ) or k.arg is None:
                    out.append(f"{module}:{node.lineno} {ast.unparse(node)}")
    return out


def _all(check) -> list[str]:
    out: list[str] = []
    for path in app_modules():
        out += check(parse(path), rel(path))
    return out


# ── the pins ───────────────────────────────────────────────────────────


def test_floor2_metric_label_names_are_the_allowed_enums() -> None:
    assert _all(label_name_problems) == []


def test_floor2_metric_label_values_are_never_identifiers_or_messages() -> None:
    assert _all(label_value_problems) == []


def test_floor2_api_instrumentator_keeps_route_templates() -> None:
    assert _all(instrumentator_problems) == []


def test_floor2_reviewed_class_name_sites_are_not_stale() -> None:
    """Every ``CLASS_NAME_LOCAL_SITES`` entry still labels that metric in that module."""
    stale = []
    for module, metric in CLASS_NAME_LOCAL_SITES:
        path = next((p for p in app_modules() if rel(p) == module), None)
        calls = [] if path is None else [c for _s, c in _labels_calls(parse(path))]
        if not any(dotted(c.func.value) == metric for c in calls):
            stale.append(f"{module}: {metric}")
    assert not stale, f"stale CLASS_NAME_LOCAL_SITES entries: {stale}"


def test_floor2_metric_policy_is_not_vacuous() -> None:
    """The checks see the real worker metrics, so a rename cannot empty them."""
    from app.pipeline import metrics

    declared = [
        m for m in vars(metrics).values() if type(m).__name__ in {"Counter", "Histogram", "Gauge"}
    ]
    assert len(declared) >= 8
    for m in declared:
        assert set(m._labelnames) <= ALLOWED_LABELS, m
    labelled = sum(
        1
        for path in app_modules()
        for n in ast.walk(parse(path))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "labels"
    )
    assert labelled >= 10
    main = next(p for p in app_modules() if rel(p) == "app/main.py")
    assert "Instrumentator" in main.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("source", "bad"),
    [
        pytest.param(
            "from prometheus_client import Counter\nC = Counter('c', 'd', ['stage'])",
            False,
            id="ok",
        ),
        pytest.param(
            "from prometheus_client import Counter\nC = Counter('c', 'd', ['user_id'])",
            True,
            id="user_id-label",
        ),
        pytest.param(
            "from prometheus_client import Histogram\nH = Histogram('h', 'd', labelnames=('email',))",
            True,
            id="email-kw",
        ),
        pytest.param(
            "from prometheus_client import Gauge\nG = Gauge('g', 'd', LABELS)",
            True,
            id="non-literal",
        ),
        pytest.param(
            "import prometheus_client as p\nC = p.Counter('c', 'd', ['artifact_id'])",
            True,
            id="module-import",
        ),
        pytest.param(
            "from collections import Counter\nC = Counter('a', 'b', ['user_id'])",
            False,
            id="collections",
        ),
    ],
)
def test_floor2_label_name_detector(source, bad) -> None:
    assert bool(label_name_problems(ast.parse(source), "x.py")) is bad


@pytest.mark.parametrize(
    ("call", "bad"),
    [
        pytest.param("M.labels(stage='classify', outcome=outcome)", False, id="ok"),
        pytest.param(
            "M.labels(stage=stage, error_class=type(exc).__name__)", False, id="class-name"
        ),
        pytest.param("M.labels(stage=stage, error_class=str(exc))", True, id="message"),
        pytest.param(
            "M.labels(stage=stage, error_class=f'{type(exc).__name__}: {exc}')", True, id="fstring"
        ),
        pytest.param(
            "M.labels(stage=stage, error_class=exc.__class__.__name__)", True, id="other-spelling"
        ),
        pytest.param("M.labels(outcome=artifact_id)", True, id="identifier-name"),
        pytest.param("M.labels(user_id=user.id)", True, id="user-label"),
        pytest.param("M.labels('classify')", True, id="positional"),
        pytest.param("M.labels(outcome=1)", True, id="non-string"),
    ],
)
def test_floor2_label_value_detector(call, bad) -> None:
    assert bool(label_value_problems(ast.parse(call), "x.py")) is bad


_REVIEWED_SITE = (
    "class Refused(Exception):\n    pass\n\n"
    "def f(exc):\n{body}    CLI_SPAWN_REFUSALS.labels(stage='s', error_class=name)\n"
)


@pytest.mark.parametrize(
    ("module", "body", "bad"),
    [
        pytest.param("app/agents/claude_code.py", "    name = Refused.__name__\n", False, id="ok"),
        pytest.param("x.py", "    name = Refused.__name__\n", True, id="unreviewed-module"),
        pytest.param("app/agents/claude_code.py", "    name = str(exc)\n", True, id="message"),
        pytest.param(
            "app/agents/claude_code.py",
            "    name = Refused.__name__\n    name = str(exc)\n",
            True,
            id="rebound",
        ),
        pytest.param(
            "app/agents/claude_code.py", "    name = Elsewhere.__name__\n", True, id="foreign-class"
        ),
        pytest.param("app/agents/claude_code.py", "", True, id="unbound"),
    ],
)
def test_floor2_reviewed_class_name_site_detector(module, body, bad) -> None:
    """The reviewed spelling is accepted only as reviewed: bound once, from a local class."""
    tree = ast.parse(_REVIEWED_SITE.format(body=body))
    assert bool(label_value_problems(tree, module)) is bad


@pytest.mark.parametrize(
    ("call", "bad"),
    [
        pytest.param("Instrumentator()", False, id="default"),
        pytest.param("Instrumentator(should_group_untemplated=False)", True, id="raw-paths"),
        pytest.param("Instrumentator(**opts)", True, id="opaque"),
    ],
)
def test_floor2_instrumentator_detector(call, bad) -> None:
    assert bool(instrumentator_problems(ast.parse(call), "x.py")) is bad


async def test_floor1_api_metrics_name_route_templates_not_raw_paths() -> None:
    """With main.py's (default) settings, an id in the path never reaches /metrics."""
    from fastapi import FastAPI
    from prometheus_client import CollectorRegistry, generate_latest
    from prometheus_fastapi_instrumentator import Instrumentator

    app = FastAPI()

    @app.get("/api/courses/{code}/weeks/{week}")
    async def week(code: str, week: int) -> dict:
        return {}

    registry = CollectorRegistry()
    Instrumentator(registry=registry).instrument(app)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/courses/VICTIM-COURSE-7/weeks/3")
        await client.get("/api/users/alice@example.com/raw-unmatched-path")

    body = generate_latest(registry).decode()
    assert 'handler="/api/courses/{code}/weeks/{week}"' in body
    for leaked in ("VICTIM-COURSE-7", "alice@example.com", "raw-unmatched-path"):
        assert leaked not in body

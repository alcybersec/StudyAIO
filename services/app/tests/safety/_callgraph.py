"""A static, intra-``app`` call graph for floor checks that follow a task's reach.

Built from source with :mod:`ast` (nothing is imported), so it is independent of
Celery, Redis and Postgres. A node is ``(module, qualname)`` with ``module`` a
dotted ``app.*`` name and ``qualname`` a top-level function or ``Class.method``.

Edges come from every name a function body mentions (calls, callbacks passed as
arguments, function-local imports included) that resolves to a function or class
in ``app``. A class reference reaches all of its methods. Import chains through
package ``__init__`` re-exports are followed.

**Celery task references are not edges** unless the task object is *called*
directly (``task(...)`` or ``task.run(...)``). ``task.s()``, ``.delay()`` and
``.apply_async()`` enqueue: the task runs on the queue it is routed to, and the
routing check covers it there. Without this rule ``recover_stuck_artifacts``
(which re-enqueues the upload chain) would appear to call the agent itself.

Limits (the graph under-approximates, so tests that use it pin a known-positive
set as well, to show it is not blind): attribute calls on instances
(``obj.method()``) and functions reached only through module-level containers
(a dict of callables) are not followed.
"""

from __future__ import annotations

import ast
import functools
import pathlib
from collections.abc import Iterable

from tests.safety._source import APP_ROOT, dotted, parse

Node = tuple[str, str]

_ENQUEUE_ATTRS = frozenset({"s", "si", "signature", "delay", "apply_async", "map", "starmap"})


def module_path(module: str) -> pathlib.Path | None:
    """File for a dotted ``app.*`` module, or ``None`` if it is not one."""
    if module != "app" and not module.startswith("app."):
        return None
    parts = module.split(".")[1:]
    base = APP_ROOT.joinpath(*parts)
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def _is_task(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for dec in fn.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if dotted(target).split(".")[-1] in {"task", "shared_task"}:
            return True
    return False


class _Module:
    """Definitions and module-level imports of one ``app`` module."""

    def __init__(self, name: str, tree: ast.Module) -> None:
        self.name = name
        self.tree = tree
        self.functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
        self.classes: dict[str, ast.ClassDef] = {}
        self.tasks: set[str] = set()
        self.imports: dict[str, tuple[str, str | None]] = {}
        for stmt in tree.body:
            if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef):
                self.functions[stmt.name] = stmt
                if _is_task(stmt):
                    self.tasks.add(stmt.name)
            elif isinstance(stmt, ast.ClassDef):
                self.classes[stmt.name] = stmt
        self.imports = _imports(name, tree.body, nested=False)


def _imports(module: str, body: Iterable[ast.AST], *, nested: bool) -> dict:
    """Local name -> (module, symbol or None for a module import)."""
    out: dict[str, tuple[str, str | None]] = {}
    nodes = ast.walk(ast.Module(body=list(body), type_ignores=[])) if nested else body
    for stmt in nodes:
        if isinstance(stmt, ast.ImportFrom):
            source = stmt.module or ""
            if stmt.level:
                pkg = module.split(".")[: -stmt.level]
                source = ".".join([*pkg, source] if source else pkg)
            for alias in stmt.names:
                out[alias.asname or alias.name] = (source, alias.name)
        elif isinstance(stmt, ast.Import):
            for alias in stmt.names:
                if alias.asname:
                    out[alias.asname] = (alias.name, None)
                else:
                    out[alias.name.split(".")[0]] = (alias.name.split(".")[0], None)
    return out


@functools.cache
def load(module: str) -> _Module | None:
    """Parsed ``app`` module, cached for the session."""
    path = module_path(module)
    if path is None:
        return None
    return _Module(module, parse(path))


def resolve(module: str, symbol: str, _depth: int = 0) -> tuple[str, str | None] | None:
    """Where ``module.symbol`` is defined: ``(module, name)``, or ``(module, None)``."""
    if _depth > 10:
        return None
    mod = load(module)
    if mod is None:
        return None
    if symbol in mod.functions or symbol in mod.classes:
        return (module, symbol)
    if symbol in mod.imports:
        src, name = mod.imports[symbol]
        return resolve(src, name, _depth + 1) if name else (src, None)
    if module_path(f"{module}.{symbol}") is not None:
        return (f"{module}.{symbol}", None)
    return None


def _resolve_local(mod: _Module, local: dict, name: str) -> tuple[str, str | None] | None:
    if name in local:
        src, sym = local[name]
        if sym is None:
            return (src, None) if load(src) else None
        return resolve(src, sym)
    if name in mod.functions or name in mod.classes:
        return (mod.name, name)
    if name in mod.imports:
        src, sym = mod.imports[name]
        if sym is None:
            return (src, None) if load(src) else None
        return resolve(src, sym)
    return None


def _definition(node: Node) -> list[ast.AST]:
    module, qual = node
    mod = load(module)
    if mod is None:
        return []
    if "." in qual:
        cls, meth = qual.split(".", 1)
        body = mod.classes.get(cls)
        return [s for s in (body.body if body else []) if getattr(s, "name", None) == meth]
    if qual in mod.functions:
        return [mod.functions[qual]]
    if qual in mod.classes:
        return [mod.classes[qual]]
    return []


def _targets(module: str, target: tuple[str, str | None], attr: str | None) -> list[Node]:
    """Graph nodes a reference resolves to."""
    src, name = target
    if name is None:  # a module; ``attr`` names the member
        if attr is None:
            return []
        hit = resolve(src, attr)
        return _targets(module, hit, None) if hit and hit[1] else []
    mod = load(src)
    if mod is None:
        return []
    if name in mod.classes:
        cls = mod.classes[name]
        methods = [
            s.name for s in cls.body if isinstance(s, ast.FunctionDef | ast.AsyncFunctionDef)
        ]
        return [(src, name)] + [(src, f"{name}.{m}") for m in methods]
    return [(src, name)]


def callees(node: Node) -> set[Node]:
    """Direct edges out of ``node`` (see the module docstring for the rules)."""
    module = node[0]
    mod = load(module)
    if mod is None:
        return set()
    out: set[Node] = set()
    for definition in _definition(node):
        local = _imports(module, getattr(definition, "body", []), nested=True)
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(definition):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent
        for sub in ast.walk(definition):
            if isinstance(sub, ast.Name):
                ref, attr, outer = _resolve_local(mod, local, sub.id), None, sub
            elif isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name):
                ref = _resolve_local(mod, local, sub.value.id)
                if ref is None or ref[1] is not None:
                    continue
                attr, outer = sub.attr, sub
            else:
                continue
            if ref is None:
                continue
            for target in _targets(module, ref, attr):
                if _enqueued(target, outer, parents):
                    continue
                out.add(target)
    out.discard(node)
    return out


def _enqueued(target: Node, ref: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    """A Celery task reference that is not a direct, in-process call."""
    mod = load(target[0])
    if mod is None or target[1] not in mod.tasks:
        return False
    parent = parents.get(ref)
    if isinstance(parent, ast.Call) and parent.func is ref:
        return False  # task(...) runs inline
    if isinstance(parent, ast.Attribute) and parent.value is ref:
        return parent.attr in _ENQUEUE_ATTRS or parent.attr != "run"
    return True


def reachable(start: Node) -> set[Node]:
    """Every node reachable from ``start``, ``start`` included."""
    seen = {start}
    stack = [start]
    while stack:
        for nxt in callees(stack.pop()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def task_node(task_name: str) -> Node:
    """``app.pipeline.x.func`` (a Celery task name) -> its graph node."""
    module, _, func = task_name.rpartition(".")
    return (module, func)

"""Static-analysis helpers shared by the floor tier.

Everything here reads source files and parses them with :mod:`ast`; nothing
imports the modules it inspects. That keeps the static floor checks independent
of import-time side effects and of whether Postgres or Redis are reachable.

Paths are reported relative to ``services/app`` (``app/api/qa.py``), the form
ADR 0003 uses for ``REQUEST_TIME_GET_AGENT_CALL_SITES``.
"""

from __future__ import annotations

import ast
import pathlib
from collections.abc import Iterator
from dataclasses import dataclass

#: ``services/app`` — the directory that contains the ``app`` package.
SERVICE_ROOT = pathlib.Path(__file__).resolve().parents[2]
APP_ROOT = SERVICE_ROOT / "app"


def rel(path: pathlib.Path) -> str:
    """``app/...`` form of a path under ``services/app``."""
    return path.resolve().relative_to(SERVICE_ROOT).as_posix()


def app_modules(*, exclude: tuple[str, ...] = ()) -> list[pathlib.Path]:
    """Every ``.py`` file under ``app/``, minus any whose rel path starts with ``exclude``."""
    out = []
    for path in sorted(APP_ROOT.rglob("*.py")):
        r = rel(path)
        if any(r.startswith(prefix) for prefix in exclude):
            continue
        out.append(path)
    return out


def parse(path: pathlib.Path) -> ast.Module:
    """Parse one source file."""
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


@dataclass(frozen=True)
class Site:
    """One AST node located by module, enclosing function and line."""

    module: str
    function: str
    lineno: int
    text: str

    def key(self) -> tuple[str, str]:
        """The ``(module, enclosing function)`` pair ADR 0003 keys on."""
        return (self.module, self.function)

    def __str__(self) -> str:
        return f"{self.module}:{self.lineno} in {self.function}(): {self.text}"


def walk_with_scope(tree: ast.AST) -> Iterator[tuple[ast.AST, str]]:
    """Yield ``(node, qualname)`` for every node, qualname of its innermost def.

    Module-level code reports ``<module>``. Nested defs and methods are dotted
    (``Outer.inner``), so moving a call into a closure changes its key — which
    for an allowlist is the conservative direction.
    """

    def visit(node: ast.AST, scope: list[str]) -> Iterator[tuple[ast.AST, str]]:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                inner = [*scope, child.name]
                yield child, ".".join(scope) or "<module>"
                yield from visit(child, inner)
            else:
                yield child, ".".join(scope) or "<module>"
                yield from visit(child, scope)

    yield from visit(tree, [])


def docstring_nodes(tree: ast.AST) -> set[int]:
    """``id()`` of every Constant node that is a docstring."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
            and node.body
        ):
            first = node.body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                ids.add(id(first.value))
    return ids


def dotted(node: ast.AST) -> str:
    """``a.b.c`` for a Name/Attribute chain, else ``""``."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    if isinstance(node, ast.Call):
        inner = dotted(node.func)
        if inner:
            parts.append(f"{inner}()")
            return ".".join(reversed(parts))
    return ""

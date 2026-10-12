"""Shared readers for the weak-spot engine contracts (ADR 0007, docs/CONTRACTS.md).

The four ``test_weakspot_*`` / ``test_targeted_generation_contract`` files each pin
one provider's half of ADR 0007 (``backend`` service and API, ``ai`` worker,
``data`` storage). They read the same two documents, so the parsing lives here
once. Not a test module (no ``test_`` prefix), so pytest does not collect it.
"""

import ast
import os
import re
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = APP_ROOT / "app"
REPO_ROOT = APP_ROOT.parents[1]
ADR_0007_PATH = REPO_ROOT / "docs" / "adr" / "0007-weak-spot-engine.md"
ADR_0003_PATH = REPO_ROOT / "docs" / "adr" / "0003-floor3-request-time-ai-calls.md"
CONTRACTS_PATH = REPO_ROOT / "docs" / "CONTRACTS.md"

_PYTHON_BLOCK = re.compile(r"^```python\n(.*?)^```", flags=re.DOTALL | re.MULTILINE)


def require(path: Path, why: str = "docs/ is not mounted in the container") -> str:
    """Read a repo doc, failing in CI and skipping elsewhere when absent.

    Same rule as ``test_agent_adapter_contract._require``: the API container
    mounts ``tests/`` but not ``docs/``.

    Args:
        path: The document.
        why: Why it may legitimately be absent.

    Returns:
        The document's text.
    """
    if path.is_file():
        return path.read_text(encoding="utf-8")
    message = f"{path} not found ({why})"
    if os.environ.get("CI"):
        pytest.fail(message)
    pytest.skip(message)


def python_block(text: str, where: str) -> ast.Module:
    """Parse the single ``python`` block of a document or section.

    Args:
        text: Markdown text.
        where: Name for the assertion message.

    Returns:
        The parsed block.
    """
    blocks = _PYTHON_BLOCK.findall(text)
    assert len(blocks) == 1, f"expected one python block in {where}, found {len(blocks)}"
    return ast.parse(blocks[0])


def contract_section(heading: str) -> str:
    """Return one ``###`` entry of docs/CONTRACTS.md, up to the next heading.

    Args:
        heading: The full heading line, e.g. ``"### api.weak-spots v1"``.

    Returns:
        The entry's body.
    """
    text = require(CONTRACTS_PATH)
    start = text.find(heading + "\n")
    assert start != -1, f"{heading!r} missing from {CONTRACTS_PATH}"
    rest = text[start + len(heading) :]
    end = re.search(r"^#{2,3} ", rest, flags=re.MULTILINE)
    return rest[: end.start()] if end else rest


def table_rows(text: str, header_first_cell: str) -> list[list[str]]:
    """Body rows of the first markdown table whose header starts with a cell.

    A ``\\|`` inside a cell is kept as a literal ``|``.

    Args:
        text: Markdown text.
        header_first_cell: Exact text of the header's first cell.

    Returns:
        Each body row as a list of stripped cells.
    """

    def cells(line: str) -> list[str]:
        parts = re.split(r"(?<!\\)\|", line.strip().strip("|"))
        return [p.replace("\\|", "|").strip() for p in parts]

    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("|") and cells(line)[0] == header_first_cell:
            rows = []
            for body in lines[i + 2 :]:
                if not body.startswith("|"):
                    break
                rows.append(cells(body))
            return rows
    raise AssertionError(f"no table with first header cell {header_first_cell!r}")


def constants(tree: ast.Module) -> dict[str, object]:
    """Module-level literal assignments of a parsed block or module.

    Args:
        tree: A parsed module.

    Returns:
        Name to literal value, for every ``NAME = <literal>`` at top level.
    """
    out: dict[str, object] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                try:
                    out[target.id] = ast.literal_eval(node.value)
                except ValueError:
                    continue
    return out


def signature(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[object, ...]:
    """Source-text signature of a def, comparable across two parses.

    Includes whether the def is ``async``, so a sync implementation of an async
    stub (or the reverse) is a mismatch.
    """
    a = fn.args

    def params(args: list[ast.arg]) -> list[tuple[str, str | None]]:
        return [(p.arg, ast.unparse(p.annotation) if p.annotation else None) for p in args]

    return (
        isinstance(fn, ast.AsyncFunctionDef),
        params(a.posonlyargs),
        params(a.args),
        [ast.unparse(d) for d in a.defaults],
        a.vararg.arg if a.vararg else None,
        params(a.kwonlyargs),
        [ast.unparse(d) if d else None for d in a.kw_defaults],
        a.kwarg.arg if a.kwarg else None,
        ast.unparse(fn.returns) if fn.returns else None,
    )


def top_level(tree: ast.Module) -> dict[str, ast.stmt]:
    """Top-level functions and classes of a parsed module, by name."""
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


def dataclass_fields(cls: ast.ClassDef) -> list[tuple[str, str, str | None]]:
    """Annotated fields of a dataclass as ``(name, annotation, default)`` source text."""
    return [
        (
            node.target.id,
            ast.unparse(node.annotation),
            ast.unparse(node.value) if node.value is not None else None,
        )
        for node in cls.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    ]


def dataclass_decorator(cls: ast.ClassDef) -> str | None:
    """The ``@dataclass`` decorator of a class as source text, or None."""
    for dec in cls.decorator_list:
        text = ast.unparse(dec)
        if text == "dataclass" or text.startswith("dataclass("):
            return text
    return None

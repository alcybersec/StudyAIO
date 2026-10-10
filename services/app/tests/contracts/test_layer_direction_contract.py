"""Contract test for layer direction, ADR 0002 Decision 2.

ADR 0002 carries one ``python`` block with two literals:

* ``ALLOWED_IMPORTS`` — for each top-level unit under ``app/`` (a layer package
  such as ``services``, or an entry module such as ``main``), the units it may
  import from;
* ``KNOWN_EXCEPTIONS`` — ``(importing module, imported module)`` pairs that run
  against ``ALLOWED_IMPORTS`` and are tolerated until their scheduled fix.

The test walks every ``.py`` under ``app/`` with ``ast`` (so imports inside a
function count — a local import is still a dependency) and computes the
module-level edges that break ``ALLOWED_IMPORTS``. That set must equal
``KNOWN_EXCEPTIONS`` exactly:

* a new upward import fails here until the ADR is amended to admit it;
* a fixed exception left in the ADR also fails, so the list cannot go stale.
"""

import ast
import os
import re
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = APP_ROOT / "app"
REPO_ROOT = APP_ROOT.parents[1]
ADR_PATH = REPO_ROOT / "docs" / "adr" / "0002-module-boundaries.md"


def _require(path: Path, why: str) -> str:
    """Read a repo doc, failing in CI and skipping elsewhere when absent.

    Same rule as `test_agent_adapter_contract._require`: the API container
    mounts `tests/` but not `docs/`.
    """
    if path.is_file():
        return path.read_text(encoding="utf-8")
    message = f"{path} not found ({why})"
    if os.environ.get("CI"):
        pytest.fail(message)
    pytest.skip(message)


@pytest.fixture(scope="module")
def adr_constants() -> dict[str, object]:
    """Module-level literal assignments in ADR 0002's one `python` block."""
    text = _require(ADR_PATH, "docs/ is not mounted in the container")
    blocks = re.findall(r"^```python\n(.*?)^```", text, flags=re.DOTALL | re.MULTILINE)
    assert len(blocks) == 1, f"expected one python block in ADR 0002, found {len(blocks)}"
    constants: dict[str, object] = {}
    for node in ast.parse(blocks[0]).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                constants[target.id] = ast.literal_eval(node.value)
    return constants


def _module_name(path: Path, package_root: Path) -> str:
    """Dotted module name for a file under ``package_root`` (the ``app/`` dir)."""
    parts = list(path.relative_to(package_root.parent).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _unit(module: str) -> str:
    """Top-level unit of an ``app.*`` module: ``app.services.x`` -> ``services``."""
    return module.split(".")[1]


def _app_imports(tree: ast.AST) -> set[str]:
    """Every absolute ``app.*`` module a parsed file imports, at any depth."""
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names if a.name.startswith("app."))
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if node.module == "app":
                found.update(f"app.{a.name}" for a in node.names)
            elif node.module.startswith("app."):
                found.add(node.module)
    return found


def _violations(package_root: Path, allowed: dict[str, list[str]]) -> set[tuple[str, str]]:
    """Module-level edges whose target unit is not allowed for the source unit."""
    found: set[tuple[str, str]] = set()
    for path in sorted(package_root.rglob("*.py")):
        source = _module_name(path, package_root)
        if source == "app":
            continue
        src_unit = _unit(source)
        permitted = set(allowed[src_unit]) | {src_unit}
        for target in _app_imports(ast.parse(path.read_text(encoding="utf-8"))):
            if _unit(target) not in permitted:
                found.add((source, target))
    return found


def test_adr_block_names_every_unit(adr_constants: dict[str, object]) -> None:
    """Every package and top-level module under app/ has a row, and no extras."""
    allowed = adr_constants["ALLOWED_IMPORTS"]
    assert isinstance(allowed, dict)
    on_disk = {
        p.name if p.is_dir() else p.stem
        for p in PACKAGE_ROOT.iterdir()
        if (p.is_dir() and (p / "__init__.py").is_file())
        or (p.suffix == ".py" and p.stem != "__init__")
    }
    assert set(allowed) == on_disk, (
        "ADR 0002 ALLOWED_IMPORTS must have exactly one row per unit under app/. "
        f"Missing: {sorted(on_disk - set(allowed))}; extra: {sorted(set(allowed) - on_disk)}"
    )
    for unit, targets in allowed.items():
        unknown = set(targets) - on_disk
        assert not unknown, f"ALLOWED_IMPORTS[{unit!r}] names unknown units {sorted(unknown)}"


def test_layer_direction_matches_adr(adr_constants: dict[str, object]) -> None:
    """Upward imports in the code are exactly ADR 0002's KNOWN_EXCEPTIONS."""
    allowed = adr_constants["ALLOWED_IMPORTS"]
    exceptions = {tuple(pair) for pair in adr_constants["KNOWN_EXCEPTIONS"]}
    actual = _violations(PACKAGE_ROOT, allowed)
    new = sorted(actual - exceptions)
    stale = sorted(exceptions - actual)
    assert not new, (
        "Imports against ADR 0002 Decision 2 that the ADR does not admit "
        f"(fix the import or amend the ADR): {new}"
    )
    assert not stale, f"KNOWN_EXCEPTIONS in ADR 0002 that no longer occur (remove them): {stale}"


def test_checker_catches_an_injected_upward_import(tmp_path: Path) -> None:
    """The scanner sees a function-local import from a forbidden unit."""
    pkg = tmp_path / "app"
    (pkg / "core").mkdir(parents=True)
    (pkg / "api").mkdir()
    for init in (pkg / "__init__.py", pkg / "core" / "__init__.py", pkg / "api" / "__init__.py"):
        init.write_text("")
    (pkg / "core" / "leak.py").write_text("def f():\n    from app.api.deps import X\n")
    found = _violations(pkg, {"core": [], "api": ["core"]})
    assert found == {("app.core.leak", "app.api.deps")}

"""Contract test for `agents.AgentAdapter v1` in docs/CONTRACTS.md.

The entry is the source of truth for the interface between `ai` (which owns
`app/agents/`) and its consumers in `ai` and `backend`. These tests parse the
entry's `python` block, backend table and consumer table, and compare each
against the code. Changing either side without the other fails here, which is
the point: a contract change is a version bump in CONTRACTS.md first.

Signatures are compared as source text (via `ast.unparse`) rather than as
runtime objects, so `list[str] | None` in the doc must match `list[str] | None`
in `base.py` exactly — no import-path noise, no evaluation of annotations.
"""

import ast
import importlib
import inspect
import os
import re
from fnmatch import fnmatch
from pathlib import Path

import pytest

from app.agents.base import AgentAdapter
from app.agents.factory import get_agent
from app.services.settings_service import BACKEND_REQUIRED_KEY

APP_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = APP_ROOT.parents[1]
CONTRACTS_PATH = REPO_ROOT / "docs" / "CONTRACTS.md"
STRATEGY_PATH = REPO_ROOT / "docs" / "strategy.md"
BASE_PATH = APP_ROOT / "app" / "agents" / "base.py"
FACTORY_PATH = APP_ROOT / "app" / "agents" / "factory.py"

CONTRACT_HEADING = "### agents.AgentAdapter v1"

#: Names that make a `from app.agents import X` an import of this contract.
#: `parsing` and `embeddings` are separate helpers, not part of it.
PACKAGE_EXPORTS = frozenset(
    {
        "AgentAdapter",
        "AnswerResult",
        "ClassificationResult",
        "ExtractionData",
        "FlashcardData",
        "QuizQuestionData",
        "SummaryResult",
        "get_agent",
    }
)
CONTRACT_MODULES = frozenset({"app.agents.base", "app.agents.factory"})

#: A dummy credential for every backend, so `get_agent` can build each one
#: without touching the environment or the network.
ALL_BACKEND_SETTINGS = {
    "claude_cli_credentials": "{}",
    "claude_code_path": "claude",
    "claude_model": "contract-model",
    "anthropic_api_key": "contract-key",
    "openai_api_key": "contract-key",
    "openai_model": "contract-model",
    "zai_api_key": "contract-key",
    "zai_model": "contract-model",
    "zai_base_url": "http://localhost/",
    "ollama_base_url": "http://localhost:11434",
    "ollama_model": "contract-model",
}


# ── Parsing ────────────────────────────────────────────────────────


def _require(path: Path, why: str) -> str:
    """Read a repo doc, failing in CI and skipping elsewhere when absent.

    The docs live at the repo root, outside `services/app/`. A run inside the
    API container has `tests/` mounted but not `docs/`, so locally a missing
    file is a skip. In CI the full checkout is present, so a missing file is a
    real failure and must not be skipped away.
    """
    if path.is_file():
        return path.read_text(encoding="utf-8")
    message = f"{path} not found ({why})"
    if os.environ.get("CI"):
        pytest.fail(message)
    pytest.skip(message)


@pytest.fixture(scope="module")
def section() -> str:
    """The `agents.AgentAdapter v1` section of docs/CONTRACTS.md."""
    text = _require(CONTRACTS_PATH, "docs/ is not mounted in the container")
    start = text.find(CONTRACT_HEADING + "\n")
    assert start != -1, f"{CONTRACT_HEADING!r} missing from {CONTRACTS_PATH}"
    rest = text[start + len(CONTRACT_HEADING) :]
    end = re.search(r"^#{2,3} ", rest, flags=re.MULTILINE)
    return rest[: end.start()] if end else rest


@pytest.fixture(scope="module")
def contract_tree(section: str) -> ast.Module:
    """The entry's `python` block, parsed."""
    blocks = re.findall(r"^```python\n(.*?)^```", section, flags=re.DOTALL | re.MULTILINE)
    assert len(blocks) == 1, f"expected one python block in the entry, found {len(blocks)}"
    return ast.parse(blocks[0])


@pytest.fixture(scope="module")
def base_tree() -> ast.Module:
    """`app/agents/base.py`, parsed."""
    return ast.parse(BASE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def factory_tree() -> ast.Module:
    """`app/agents/factory.py`, parsed."""
    return ast.parse(FACTORY_PATH.read_text(encoding="utf-8"))


def _table_rows(section: str, header_first_cell: str) -> list[list[str]]:
    """Return the body rows of the markdown table whose header starts with a cell.

    Args:
        section: The contract section text.
        header_first_cell: The exact text of the header's first cell.

    Returns:
        Each body row as a list of stripped cell strings.
    """
    lines = section.splitlines()
    for i, line in enumerate(lines):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and cells[0] == header_first_cell:
            rows = []
            for body in lines[i + 2 :]:
                if not body.startswith("|"):
                    break
                rows.append([c.strip() for c in body.strip().strip("|").split("|")])
            return rows
    raise AssertionError(f"no table headed {header_first_cell!r} in the contract entry")


def _ticked(cell: str) -> str:
    """Strip the backticks from a single-code-span table cell."""
    match = re.fullmatch(r"`([^`]+)`", cell.split(" ")[0])
    assert match, f"expected a backticked value, got {cell!r}"
    return match.group(1)


def _class(tree: ast.Module, name: str) -> ast.ClassDef:
    """Find a top-level class by name."""
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise AssertionError(f"class {name} not found")


def _function(tree: ast.Module | ast.ClassDef, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    """Find a function by name directly in a module or class body."""
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function {name} not found")


def _public_methods(cls: ast.ClassDef) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    """Public functions defined in a class body, keyed by name."""
    return {
        node.name: node
        for node in cls.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and not node.name.startswith("_")
    }


def _annotation(node: ast.expr | None) -> str | None:
    """Annotation source with string quotes dropped, so `"T"` equals `T`."""
    return None if node is None else ast.unparse(node).replace('"', "").replace("'", "")


def _signature(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> dict:
    """Everything about a function that a caller depends on, as comparable data."""
    args = fn.args
    positional = [*args.posonlyargs, *args.args]
    return {
        "async": isinstance(fn, ast.AsyncFunctionDef),
        "decorators": sorted(ast.unparse(d) for d in fn.decorator_list),
        "params": [(a.arg, _annotation(a.annotation)) for a in positional],
        "defaults": [ast.unparse(d) for d in args.defaults],
        "kwonly": [(a.arg, _annotation(a.annotation)) for a in args.kwonlyargs],
        "kw_defaults": [None if d is None else ast.unparse(d) for d in args.kw_defaults],
        "vararg": args.vararg.arg if args.vararg else None,
        "kwarg": args.kwarg.arg if args.kwarg else None,
        "returns": _annotation(fn.returns),
    }


def _dataclasses(tree: ast.Module) -> dict[str, list[tuple[str, str | None, str | None]]]:
    """Top-level `@dataclass` classes and their fields as (name, type, default)."""
    found = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and any(
            ast.unparse(d) == "dataclass" for d in node.decorator_list
        ):
            found[node.name] = [
                (
                    ast.unparse(item.target),
                    _annotation(item.annotation),
                    None if item.value is None else ast.unparse(item.value),
                )
                for item in node.body
                if isinstance(item, ast.AnnAssign)
            ]
    return found


# ── The interface ──────────────────────────────────────────────────


class TestAdapterInterface:
    """The `AgentAdapter` class in the entry matches `app/agents/base.py`."""

    def test_public_surface_is_exactly_the_contract(self, contract_tree, base_tree):
        """No public member is added to, or dropped from, the ABC without the entry."""
        declared = set(_public_methods(_class(contract_tree, "AgentAdapter")))
        actual = set(_public_methods(_class(base_tree, "AgentAdapter")))
        assert actual == declared, (
            f"undeclared in CONTRACTS.md: {sorted(actual - declared)}; "
            f"declared but missing from base.py: {sorted(declared - actual)}"
        )

    def test_every_member_signature_matches(self, contract_tree, base_tree):
        """Parameters, annotations, defaults, decorators and return types all agree."""
        declared = _public_methods(_class(contract_tree, "AgentAdapter"))
        actual = _public_methods(_class(base_tree, "AgentAdapter"))
        mismatches = {
            name: {"contract": _signature(fn), "base.py": _signature(actual[name])}
            for name, fn in declared.items()
            if name in actual and _signature(fn) != _signature(actual[name])
        }
        assert not mismatches, f"signature drift: {mismatches}"

    def test_abstract_set_matches_runtime(self, contract_tree):
        """The methods marked abstract in the entry are the ones Python enforces."""
        declared = {
            name
            for name, fn in _public_methods(_class(contract_tree, "AgentAdapter")).items()
            if "abstractmethod" in _signature(fn)["decorators"]
        }
        assert declared == set(AgentAdapter.__abstractmethods__)

    def test_stream_answer_is_an_async_generator(self):
        """Consumers iterate it with `async for`; a coroutine would break them."""
        assert inspect.isasyncgenfunction(AgentAdapter.stream_answer)

    def test_get_agent_signature_matches(self, contract_tree, factory_tree):
        """The factory is part of the contract: it is how consumers get an adapter."""
        declared = _signature(_function(contract_tree, "get_agent"))
        assert _signature(_function(factory_tree, "get_agent")) == declared


class TestDataTypes:
    """The data types in the entry match the dataclasses in `base.py`."""

    def test_same_set_of_types(self, contract_tree, base_tree):
        """A new or removed result type is a contract change."""
        assert set(_dataclasses(base_tree)) == set(_dataclasses(contract_tree))

    def test_fields_match(self, contract_tree, base_tree):
        """Field names, order, types and defaults agree for every type."""
        declared = _dataclasses(contract_tree)
        actual = _dataclasses(base_tree)
        drift = {
            name: (declared[name], actual[name])
            for name in declared
            if name in actual and declared[name] != actual[name]
        }
        assert not drift, f"field drift (contract, base.py): {drift}"


# ── Backends ───────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def backends(section: str) -> dict[str, tuple[type, Path]]:
    """`agent_backend` value → (adapter class, module path), from the entry's table."""
    result = {}
    for backend, cls_name, module_path in _table_rows(section, "`agent_backend`"):
        path = REPO_ROOT / _ticked(module_path)
        assert path.is_file(), f"{path} listed for {backend} does not exist"
        module_name = ".".join(path.relative_to(APP_ROOT).with_suffix("").parts)
        cls = getattr(importlib.import_module(module_name), _ticked(cls_name))
        result[_ticked(backend)] = (cls, path)
    return result


class TestBackends:
    """Every backend the factory can build is listed, concrete and conforming."""

    def test_table_matches_the_factory(self, backends):
        """The factory's backend keys are exactly the backends in the entry."""
        assert set(backends) == set(BACKEND_REQUIRED_KEY)

    def test_every_adapter_subclass_is_listed(self, backends):
        """A new adapter class in `app/agents/` cannot ship unrecorded."""
        for path in (APP_ROOT / "app" / "agents").glob("*.py"):
            importlib.import_module(f"app.agents.{path.stem}")

        def subclasses(cls: type) -> set[type]:
            direct = set(cls.__subclasses__())
            return direct.union(*(subclasses(c) for c in direct))

        in_app = {c for c in subclasses(AgentAdapter) if c.__module__.startswith("app.agents.")}
        assert in_app == {cls for cls, _ in backends.values()}

    def test_every_backend_is_concrete(self, backends):
        """No backend leaves an abstract method unimplemented."""
        abstract = {
            name: sorted(cls.__abstractmethods__)
            for name, (cls, _) in backends.items()
            if inspect.isabstract(cls)
        }
        assert not abstract, f"abstract methods left unimplemented: {abstract}"

    def test_overrides_keep_the_base_signature(self, backends, contract_tree):
        """Consumers pass keyword arguments, so a renamed parameter is a break."""
        members = _public_methods(_class(contract_tree, "AgentAdapter"))
        drift = []
        for backend, (cls, _) in backends.items():
            for name in members:
                base_member = inspect.getattr_static(AgentAdapter, name)
                if isinstance(base_member, property):
                    assert isinstance(inspect.getattr_static(cls, name), property), (
                        f"{backend}.{name}"
                    )
                    continue
                if inspect.signature(getattr(cls, name)) != inspect.signature(
                    getattr(AgentAdapter, name)
                ):
                    drift.append(f"{backend}.{name}{inspect.signature(getattr(cls, name))}")
            if not inspect.isasyncgenfunction(cls.stream_answer):
                drift.append(f"{backend}.stream_answer is not an async generator")
        assert not drift, f"backends diverge from AgentAdapter: {drift}"

    def test_factory_builds_each_listed_backend(self, backends):
        """`get_agent` maps each `agent_backend` value to the class the entry names."""
        for backend, (cls, _) in backends.items():
            agent = get_agent(user_settings={"agent_backend": backend, **ALL_BACKEND_SETTINGS})
            assert type(agent) is cls, f"{backend} built {type(agent).__name__}, not {cls.__name__}"


# ── Consumers ──────────────────────────────────────────────────────


def _imports_contract(tree: ast.Module) -> bool:
    """Whether a module imports anything from this contract, at any depth."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in CONTRACT_MODULES:
            return True
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == "app.agents"
            and any(alias.name in PACKAGE_EXPORTS for alias in node.names)
        ):
            return True
        if isinstance(node, ast.Import) and any(a.name in CONTRACT_MODULES for a in node.names):
            return True
    return False


@pytest.fixture(scope="module")
def consumer_rows(section: str) -> dict[str, tuple[str, str]]:
    """Repo-relative consumer path → (owner role, uses), from the entry's table."""
    return {
        _ticked(module): (_ticked(owner), uses)
        for module, owner, uses in _table_rows(section, "Module")
    }


class TestConsumers:
    """The entry names its consumers, and names all of them."""

    def test_entry_declares_consumers(self, section, consumer_rows):
        """§8: every entry names its consumers."""
        assert re.search(r"^Consumers: ", section, flags=re.MULTILINE)
        assert consumer_rows

    def test_listed_consumers_exist(self, consumer_rows):
        """A listed path that no longer exists is a stale entry."""
        missing = [p for p in consumer_rows if not (REPO_ROOT / p).is_file()]
        assert not missing, f"listed consumers that do not exist: {missing}"

    def test_list_matches_the_importers(self, consumer_rows):
        """Every importer is listed; every listed non-importer is marked duck-typed."""
        importers = set()
        for path in (APP_ROOT / "app").rglob("*.py"):
            if "agents" in path.relative_to(APP_ROOT / "app").parts[:1]:
                continue
            if _imports_contract(ast.parse(path.read_text(encoding="utf-8"))):
                importers.add(path.relative_to(REPO_ROOT).as_posix())
        unlisted = importers - set(consumer_rows)
        assert not unlisted, (
            f"modules import AgentAdapter's contract but are not listed: {sorted(unlisted)}"
        )
        unexplained = [
            p for p in set(consumer_rows) - importers if "duck-typed" not in consumer_rows[p][1]
        ]
        assert not unexplained, f"listed but neither importing nor marked duck-typed: {unexplained}"

    def test_owners_match_the_ownership_map(self, consumer_rows):
        """Each consumer's Owner column is the role §2 of docs/strategy.md assigns it."""
        if not STRATEGY_PATH.is_file():
            pytest.skip(f"{STRATEGY_PATH} not present in this checkout")
        globs: list[tuple[str, str]] = []
        for line in STRATEGY_PATH.read_text(encoding="utf-8").splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) == 3 and re.fullmatch(r"`[a-z]+`", cells[0]):
                role = cells[0].strip("`")
                globs += [(g, role) for g in re.findall(r"`([^`]+)`", cells[1])]
        assert globs, "could not read the §2 ownership table"

        def owner(path: str) -> str | None:
            for pattern, role in globs:
                if pattern.endswith("/**") and path.startswith(pattern[:-2]):
                    return role
                if fnmatch(path, pattern):
                    return role
            return None

        wrong = {
            p: (declared, owner(p))
            for p, (declared, _) in consumer_rows.items()
            if owner(p) != declared
        }
        assert not wrong, f"Owner column disagrees with §2 (declared, §2): {wrong}"

"""Contract test for the clock policy, ADR 0006 (ruling R-023).

ADR 0006 puts every "what time / what day is it" question behind one module,
``app/core/clock.py``. Stored timestamps are UTC-aware; a date boundary is
either the user's local day (``user_today``) or the UTC day (``utc_today``),
and the ADR says which domain uses which. That only holds if nothing else in
the app asks the host clock directly, because the host clock answers in the
container's zone (or naive), which is neither.

Two checks:

1. **No ambient clock reads outside clock.py.** Every ``.py`` under
   ``services/app/app/`` is walked with ``ast`` (function-local code and
   lambdas included) for the four banned forms:

   * ``date.today()``
   * ``datetime.today()``
   * ``datetime.utcnow()``
   * ``datetime.now()`` with no zone (no argument, or ``None``)

   in every spelling the import allows (``datetime.datetime.now()``,
   ``import datetime as dt; dt.date.today()``, ``from datetime import
   datetime as D; D.utcnow()``), and also as an uncalled reference
   (``default=datetime.utcnow``), which SQLAlchemy or a ``Field`` calls
   later with the same result. ``CLOCK_EXEMPT`` in the ADR lists the only
   files allowed to contain them.

2. **clock.py's public surface is exactly the ADR's.** The stubs in ADR
   0006's ``python`` block are compared, by name and by signature (parameter
   names, defaults, annotations, return annotation, as source text), with the
   public top-level definitions in ``app/core/clock.py``. A new public helper
   is a new contract and needs the ADR amended first. A few semantic pins
   follow (aware results, ``None``/invalid zone -> UTC, ``valid_timezone``
   never raises).

The detector is itself tested on a planted file (``TestDetector``), so a
green check 1 means "no offenders", not "the walker matched nothing".
"""

import ast
import os
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = APP_ROOT / "app"
CLOCK_PATH = PACKAGE_ROOT / "core" / "clock.py"
REPO_ROOT = APP_ROOT.parents[1]
ADR_PATH = REPO_ROOT / "docs" / "adr" / "0006-clock-policy.md"

#: Methods banned whatever their arguments, keyed by the class they hang off.
_ALWAYS_BANNED = {
    ("date", "today"): "date.today()",
    ("datetime", "today"): "datetime.today()",
    ("datetime", "utcnow"): "datetime.utcnow()",
}


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


def _adr_block() -> ast.Module:
    text = _require(ADR_PATH, "docs/ is not mounted in the container")
    blocks = re.findall(r"^```python\n(.*?)^```", text, flags=re.DOTALL | re.MULTILINE)
    assert len(blocks) == 1, f"expected one python block in ADR 0006, found {len(blocks)}"
    return ast.parse(blocks[0])


@pytest.fixture(scope="module")
def adr_block() -> ast.Module:
    """The parsed `python` block of ADR 0006."""
    return _adr_block()


@pytest.fixture(scope="module")
def adr_constants(adr_block: ast.Module) -> dict[str, object]:
    """Module-level literal assignments in ADR 0006's `python` block."""
    constants: dict[str, object] = {}
    for node in adr_block.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                constants[target.id] = ast.literal_eval(node.value)
    return constants


# --------------------------------------------------------------------------- #
# Detector
# --------------------------------------------------------------------------- #


class _Aliases:
    """What the names in one file mean, as far as ``datetime`` goes."""

    def __init__(self, tree: ast.AST) -> None:
        self.modules: set[str] = set()  # names bound to the datetime module
        self.classes: dict[str, str] = {}  # local name -> "date" | "datetime"
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "datetime":
                        self.modules.add(alias.asname or "datetime")
            elif isinstance(node, ast.ImportFrom) and node.module == "datetime" and node.level == 0:
                for alias in node.names:
                    if alias.name in ("date", "datetime"):
                        self.classes[alias.asname or alias.name] = alias.name

    def cls(self, node: ast.expr) -> str | None:
        """``"date"``/``"datetime"`` if ``node`` names that class, else None."""
        if isinstance(node, ast.Name):
            return self.classes.get(node.id)
        if (
            isinstance(node, ast.Attribute)
            and node.attr in ("date", "datetime")
            and isinstance(node.value, ast.Name)
            and node.value.id in self.modules
        ):
            return node.attr
        return None


def _is_none(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def _naive_now_call(call: ast.Call) -> bool:
    """True if ``<datetime>.now(...)`` is given no zone (or ``None``)."""
    tz_args = list(call.args[:1]) + [k.value for k in call.keywords if k.arg == "tz"]
    if any(k.arg is None for k in call.keywords):  # **kwargs: cannot tell, do not guess
        return False
    return not tz_args or all(_is_none(a) for a in tz_args)


def find_clock_reads(source: str, filename: str = "<planted>") -> list[tuple[int, str]]:
    """Every banned ambient clock read in ``source`` as ``(line, form)``.

    Args:
        source: Python source text.
        filename: Used only in syntax-error messages.

    Returns:
        Sorted ``(lineno, description)`` pairs; empty when the file is clean.
    """
    tree = ast.parse(source, filename=filename)
    aliases = _Aliases(tree)
    called: set[int] = set()
    found: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        cls = aliases.cls(node.func.value)
        if cls is None:
            continue
        called.add(id(node.func))
        key = (cls, node.func.attr)
        if key in _ALWAYS_BANNED:
            found.append((node.lineno, _ALWAYS_BANNED[key]))
        elif key == ("datetime", "now") and _naive_now_call(node):
            found.append((node.lineno, "naive datetime.now()"))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or id(node) in called:
            continue
        cls = aliases.cls(node.value)
        if cls is None:
            continue
        key = (cls, node.attr)
        if key in _ALWAYS_BANNED:
            found.append((node.lineno, f"reference to {_ALWAYS_BANNED[key][:-2]}"))
        elif key == ("datetime", "now"):
            found.append((node.lineno, "reference to datetime.now (naive when called)"))

    return sorted(found)


def _scan_app(exempt: set[str]) -> dict[str, list[tuple[int, str]]]:
    offenders: dict[str, list[tuple[int, str]]] = {}
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        rel = path.relative_to(APP_ROOT).as_posix()
        if rel in exempt:
            continue
        hits = find_clock_reads(path.read_text(encoding="utf-8"), rel)
        if hits:
            offenders[rel] = hits
    return offenders


class TestDetector:
    """The walker must see every banned form, and only those."""

    PLANTED = """\
import datetime
import datetime as dt
from datetime import date, datetime as DT, timezone, UTC
from datetime import date as D

a = date.today()                                  # 6
b = DT.today()                                    # 7
c = DT.utcnow()                                   # 8
d = DT.now()                                      # 9
e = DT.now(None)                                  # 10
f = DT.now(tz=None)                               # 11
g = datetime.datetime.now()                       # 12
h = dt.date.today()                               # 13
i = D.today()                                     # 14

def local():
    def inner():
        return dt.datetime.utcnow()               # 18
    return (lambda: DT.now())()                   # 19

class Model:
    created = Column(default=DT.utcnow)           # 22
    stamped = Column(default=DT.now)              # 23
    day = Field(default_factory=date.today)       # 24

ok1 = DT.now(UTC)
ok2 = DT.now(timezone.utc)
ok3 = DT.now(tz=some_zone)
ok4 = datetime.datetime.now(UTC)
ok5 = DT.fromisoformat("2026-01-01T00:00:00+00:00")
ok6 = date(2026, 1, 1)
ok7 = DT.now(**kwargs)
"""

    EXPECTED = [
        (6, "date.today()"),
        (7, "datetime.today()"),
        (8, "datetime.utcnow()"),
        (9, "naive datetime.now()"),
        (10, "naive datetime.now()"),
        (11, "naive datetime.now()"),
        (12, "naive datetime.now()"),
        (13, "date.today()"),
        (14, "date.today()"),
        (18, "datetime.utcnow()"),
        (19, "naive datetime.now()"),
        (22, "reference to datetime.utcnow"),
        (23, "reference to datetime.now (naive when called)"),
        (24, "reference to date.today"),
    ]

    def test_catches_every_banned_form_and_nothing_else(self):
        assert find_clock_reads(self.PLANTED) == self.EXPECTED

    def test_unrelated_names_are_not_matched(self):
        source = (
            "class date:\n"
            "    @staticmethod\n"
            "    def today(): ...\n"
            "x = date.today()\n"
            "import arrow\n"
            "y = arrow.now()\n"
            "z = pendulum.datetime.now()\n"
        )
        assert find_clock_reads(source) == []

    def test_scan_covers_the_package(self):
        """The walk sees real files, so an empty result is meaningful."""
        files = list(PACKAGE_ROOT.rglob("*.py"))
        assert len(files) > 100
        assert any(p.name == "streak_service.py" for p in files)


class TestNoAmbientClock:
    def test_exempt_list_is_only_clock_module(self, adr_constants):
        assert adr_constants["CLOCK_EXEMPT"] == {"app/core/clock.py"}

    def test_no_ambient_clock_reads_outside_clock_module(self, adr_constants):
        offenders = _scan_app(set(adr_constants["CLOCK_EXEMPT"]))
        lines = [f"  {f}:{n}  {form}" for f, hits in offenders.items() for n, form in hits]
        assert not offenders, (
            "Ambient clock reads outside app/core/clock.py (ADR 0006). Use "
            "utc_now()/utc_today() for UTC questions and user_now(tz)/user_today(tz) "
            f"for user-facing ones:\n{len(lines)} hit(s) in {len(offenders)} file(s)\n"
            + "\n".join(lines)
        )


# --------------------------------------------------------------------------- #
# Surface
# --------------------------------------------------------------------------- #


def _signature(fn: ast.FunctionDef) -> tuple[object, ...]:
    """Source-text signature of a def, comparable across two parses."""
    a = fn.args

    def params(args: list[ast.arg]) -> list[tuple[str, str | None]]:
        return [(p.arg, ast.unparse(p.annotation) if p.annotation else None) for p in args]

    return (
        params(a.posonlyargs),
        params(a.args),
        [ast.unparse(d) for d in a.defaults],
        a.vararg.arg if a.vararg else None,
        params(a.kwonlyargs),
        [ast.unparse(d) if d else None for d in a.kw_defaults],
        a.kwarg.arg if a.kwarg else None,
        ast.unparse(fn.returns) if fn.returns else None,
    )


def _public_defs(tree: ast.Module) -> dict[str, ast.stmt]:
    """Public top-level definitions (functions, classes, assignments), not imports."""
    out: dict[str, ast.stmt] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names = [node.name]
        elif isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        else:
            continue
        for name in names:
            if not name.startswith("_"):
                out[name] = node
    return out


@pytest.fixture(scope="module")
def adr_stubs(adr_block: ast.Module) -> dict[str, ast.FunctionDef]:
    stubs = {n.name: n for n in adr_block.body if isinstance(n, ast.FunctionDef)}
    assert stubs, "ADR 0006's python block defines no clock functions"
    return stubs


@pytest.fixture(scope="module")
def clock_tree() -> ast.Module:
    assert CLOCK_PATH.is_file(), (
        "app/core/clock.py does not exist yet: `backend` implements it per ADR 0006"
    )
    return ast.parse(CLOCK_PATH.read_text(encoding="utf-8"))


class TestSurface:
    def test_adr_names_the_five_functions(self, adr_stubs):
        """Guards the ADR block itself against a silent edit."""
        assert set(adr_stubs) == {
            "utc_now",
            "utc_today",
            "user_now",
            "user_today",
            "valid_timezone",
        }

    def test_public_surface_is_exactly_the_adr(self, adr_stubs, clock_tree):
        public = _public_defs(clock_tree)
        assert set(public) == set(adr_stubs), (
            "app/core/clock.py's public names differ from ADR 0006: "
            f"extra={sorted(set(public) - set(adr_stubs))} "
            f"missing={sorted(set(adr_stubs) - set(public))}. Prefix helpers with `_` "
            "or amend the ADR first."
        )

    def test_signatures_match_the_adr(self, adr_stubs, clock_tree):
        public = _public_defs(clock_tree)
        mismatched = {
            name: {"adr": _signature(stub), "clock.py": _signature(public[name])}
            for name, stub in adr_stubs.items()
            if isinstance(public.get(name), ast.FunctionDef)
            and _signature(public[name]) != _signature(stub)
        }
        not_sync_defs = sorted(
            n for n in adr_stubs if n in public and not isinstance(public[n], ast.FunctionDef)
        )
        assert not mismatched and not not_sync_defs, (mismatched, not_sync_defs)


class TestSemantics:
    """Behaviour every caller relies on. Detail beyond this is backend's unit tier."""

    @pytest.fixture(scope="class")
    def clock(self):
        from app.core import clock

        return clock

    def test_utc_now_is_aware_utc(self, clock):
        now = clock.utc_now()
        assert now.tzinfo is not None and now.utcoffset() == timedelta(0)
        assert abs(now - datetime.now(UTC)) < timedelta(seconds=5)

    def test_utc_today_is_the_utc_date(self, clock):
        assert clock.utc_today() in {
            datetime.now(UTC).date(),
            (datetime.now(UTC) - timedelta(seconds=5)).date(),
        }
        assert type(clock.utc_today()) is date

    @pytest.mark.parametrize("tz", [None, "", "Not/AZone", "../../etc/passwd", "UTC"])
    def test_none_or_invalid_zone_falls_back_to_utc(self, clock, tz):
        now = clock.user_now(tz)
        assert now.tzinfo is not None and now.utcoffset() == timedelta(0)
        assert clock.user_today(tz) in {clock.utc_today(), clock.utc_today() - timedelta(1)}

    def test_user_now_uses_the_zone(self, clock):
        assert clock.user_now("Pacific/Kiritimati").utcoffset() == timedelta(hours=14)
        assert clock.user_now("Asia/Kolkata").utcoffset() == timedelta(hours=5, minutes=30)

    def test_user_today_is_the_local_date(self, clock):
        tz = "Pacific/Kiritimati"
        assert clock.user_today(tz) in {
            clock.user_now(tz).date(),
            (clock.user_now(tz) - timedelta(seconds=5)).date(),
        }
        assert type(clock.user_today(tz)) is date

    @pytest.mark.parametrize(
        ("tz", "ok"),
        [
            ("UTC", True),
            ("Europe/Berlin", True),
            ("America/Argentina/Buenos_Aires", True),
            ("", False),
            ("Not/AZone", False),
            ("../../etc/passwd", False),
            ("/etc/localtime", False),
            ("Europe/Berlin\x00", False),
        ],
    )
    def test_valid_timezone_never_raises(self, clock, tz, ok):
        assert clock.valid_timezone(tz) is ok

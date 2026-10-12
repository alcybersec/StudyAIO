"""Contract test for `services.weakspot v1` — ADR 0007's python block and worked examples.

ADR 0007 decides the weak-spot score as a formula with named constants, and
its single ``python`` block is the contract for
``app/services/weakspot_service.py`` (owner ``backend``). This file checks:

1. **The block itself** names what the ADR says it names (guards a silent edit
   of the ADR).
2. **Constants** in the module equal the block's, value for value.
3. **Dataclasses** have the block's fields (name, annotation, default, as
   source text) and its ``@dataclass(...)`` arguments.
4. **Functions** have the block's signatures as source text, ``async`` included.
   The module may define more public names than the block; it may not lack one.
5. **The formula**: ``score_week`` reproduces every row of the ADR's
   worked-examples table, to 1e-4, and is deterministic.
6. **Dedup**: ``is_duplicate`` treats case and punctuation as noise and
   unrelated text as distinct.

Red until ``backend`` lands ``weakspot_service`` (M33-S2-BACKEND-020).
"""

import ast
import importlib
import re

import pytest

from tests.contracts._weakspot_docs import (
    ADR_0007_PATH,
    PACKAGE_ROOT,
    constants,
    dataclass_decorator,
    dataclass_fields,
    python_block,
    require,
    signature,
    table_rows,
    top_level,
)

SERVICE_PATH = PACKAGE_ROOT / "services" / "weakspot_service.py"
SERVICE_MODULE = "app.services.weakspot_service"

EXPECTED_FUNCTIONS = {
    "score_week",
    "is_duplicate",
    "get_weak_spots",
    "get_tonight_plan",
    "refresh_tonight_plan",
    "get_diagnostic_questions",
    "request_targeted_generation",
    "get_targeted_generation",
}
EXPECTED_DATACLASSES = {"QuizEvidence", "CardEvidence", "WeekScore", "WeekWeakSpot"}
#: Functions that take the caller's identity; each must take it as a required keyword (C6).
SCOPED_FUNCTIONS = EXPECTED_FUNCTIONS - {"score_week", "is_duplicate"}

TOLERANCE = 1e-4


@pytest.fixture(scope="module")
def adr_text() -> str:
    return require(ADR_0007_PATH)


@pytest.fixture(scope="module")
def adr_block(adr_text: str) -> ast.Module:
    return python_block(adr_text, "ADR 0007")


@pytest.fixture(scope="module")
def adr_defs(adr_block: ast.Module) -> dict[str, ast.stmt]:
    return top_level(adr_block)


@pytest.fixture(scope="module")
def service_tree() -> ast.Module:
    assert SERVICE_PATH.is_file(), (
        "app/services/weakspot_service.py does not exist yet: `backend` implements it per ADR 0007"
    )
    return ast.parse(SERVICE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def service():
    try:
        return importlib.import_module(SERVICE_MODULE)
    except ModuleNotFoundError as exc:
        pytest.fail(f"{SERVICE_MODULE} is not importable yet ({exc}): `backend` implements it")


# ── 1. the ADR block ───────────────────────────────────────────────────


class TestAdrBlock:
    def test_block_defines_the_expected_functions(self, adr_defs):
        fns = {n for n, d in adr_defs.items() if not isinstance(d, ast.ClassDef)}
        assert fns == EXPECTED_FUNCTIONS

    def test_block_defines_the_expected_dataclasses(self, adr_defs):
        classes = {n for n, d in adr_defs.items() if isinstance(d, ast.ClassDef)}
        assert classes == EXPECTED_DATACLASSES

    def test_scoped_functions_take_user_id_as_a_required_keyword(self, adr_defs):
        for name in SCOPED_FUNCTIONS:
            fn = adr_defs[name]
            kwonly = {
                a.arg: d for a, d in zip(fn.args.kwonlyargs, fn.args.kw_defaults, strict=True)
            }
            assert "user_id" in kwonly, f"{name}: user_id is not keyword-only"
            assert kwonly["user_id"] is None, f"{name}: user_id has a default (floor 1, C6)"

    def test_thresholds_are_ordered(self, adr_block):
        c = constants(adr_block)
        assert 0 < c["SOLID_THRESHOLD"] < c["WEAK_THRESHOLD"] < 1
        assert c["MIN_PLAN_MINUTES"] <= c["DEFAULT_PLAN_MINUTES"] <= c["MAX_PLAN_MINUTES"]
        assert c["DIAGNOSTIC_QUESTIONS"] <= c["DIAGNOSTIC_QUESTIONS_MAX"]
        assert c["CARD_EASE_WEIGHT"] + c["CARD_LAPSE_WEIGHT"] + c["CARD_OVERDUE_WEIGHT"] == 1.0

    def test_plan_costs_are_the_timed_session_costs(self):
        """ADR 0007 Decision 4 reuses these rather than defining its own."""
        from app.services import timed_session_service

        assert timed_session_service.MINUTES_PER_CARD == 2
        assert timed_session_service.MINUTES_PER_QUIZ == 3


# ── 2-4. the module matches the block ─────────────────────────────────


class TestSurface:
    def test_constants_match(self, adr_block, service_tree):
        expected = constants(adr_block)
        actual = constants(service_tree)
        wrong = {
            name: (value, actual.get(name, "<missing>"))
            for name, value in expected.items()
            if actual.get(name, "<missing>") != value
        }
        assert not wrong, f"constants differ from ADR 0007 (expected, actual): {wrong}"

    def test_dataclasses_match(self, adr_defs, service_tree):
        mine = top_level(service_tree)
        for name in EXPECTED_DATACLASSES:
            assert name in mine, f"{name} missing from weakspot_service"
            assert isinstance(mine[name], ast.ClassDef), f"{name} is not a class"
            assert dataclass_decorator(mine[name]) == dataclass_decorator(adr_defs[name]), name
            assert dataclass_fields(mine[name]) == dataclass_fields(adr_defs[name]), name

    def test_function_signatures_match(self, adr_defs, service_tree):
        mine = top_level(service_tree)
        missing = sorted(n for n in EXPECTED_FUNCTIONS if n not in mine)
        assert not missing, f"missing from weakspot_service: {missing}"
        wrong = {
            n: (signature(adr_defs[n]), signature(mine[n]))
            for n in EXPECTED_FUNCTIONS
            if signature(adr_defs[n]) != signature(mine[n])
        }
        assert not wrong, f"signatures differ from ADR 0007 (expected, actual): {wrong}"


# ── 5. the formula ─────────────────────────────────────────────────────

_QUIZ = re.compile(r"\((T|F),([\d.]+)\)(?:\s*×(\d+))?")
_CARD = re.compile(r"\(([\d.]+),(\d+),(\d+),([\d.]+)\)")


def _quiz(cell: str) -> list[tuple[bool, float]]:
    out: list[tuple[bool, float]] = []
    for correct, age, times in _QUIZ.findall(cell):
        out.extend([(correct == "T", float(age))] * int(times or 1))
    return out


def _cards(cell: str) -> list[tuple[float, int, int, float]]:
    return [(float(e), int(r), int(i), float(o)) for e, r, i, o in _CARD.findall(cell)]


def _optional_number(cell: str) -> float | None:
    return None if cell == "None" else float(cell)


@pytest.fixture(scope="module")
def worked_examples(adr_text: str) -> list[dict]:
    rows = table_rows(adr_text, "Case")
    examples = []
    for case, quiz, cards, days, status, weakness, confidence, urgency, priority in rows:
        examples.append(
            {
                "case": case,
                "quiz": _quiz(quiz),
                "cards": _cards(cards),
                "days_to_exam": None if days == "None" else int(days),
                "status": status,
                "weakness": _optional_number(weakness),
                "confidence": float(confidence),
                "urgency": float(urgency),
                "priority": float(priority),
            }
        )
    return examples


def test_worked_examples_table_is_complete(worked_examples):
    """Guards the ADR table against a row lost in an edit; each status appears."""
    assert len(worked_examples) >= 11
    assert {e["status"] for e in worked_examples} == {"unknown", "weak", "shaky", "solid"}
    assert all(e["quiz"] or e["cards"] or e["case"] == "A" for e in worked_examples)


def _score(service, example: dict):
    quiz = [service.QuizEvidence(is_correct=c, age_days=a) for c, a in example["quiz"]]
    cards = [
        service.CardEvidence(ease_factor=e, repetition_count=r, interval_days=i, overdue_days=o)
        for e, r, i, o in example["cards"]
    ]
    return service.score_week(quiz, cards, example["days_to_exam"])


def test_score_week_reproduces_the_worked_examples(service, worked_examples):
    failures = []
    for ex in worked_examples:
        got = _score(service, ex)
        problems = []
        if got.status != ex["status"]:
            problems.append(f"status {got.status!r} != {ex['status']!r}")
        if ex["weakness"] is None:
            if got.weakness is not None:
                problems.append(f"weakness {got.weakness} != None")
        elif got.weakness is None or abs(got.weakness - ex["weakness"]) > TOLERANCE:
            problems.append(f"weakness {got.weakness} != {ex['weakness']}")
        for field in ("confidence", "urgency", "priority"):
            if abs(getattr(got, field) - ex[field]) > TOLERANCE:
                problems.append(f"{field} {getattr(got, field)} != {ex[field]}")
        expected_evidence = len([q for q in ex["quiz"] if q[1] <= 90]) + len(ex["cards"])
        if got.evidence != expected_evidence:
            problems.append(f"evidence {got.evidence} != {expected_evidence}")
        if problems:
            failures.append(f"case {ex['case']}: " + "; ".join(problems))
    assert not failures, "score_week disagrees with ADR 0007:\n" + "\n".join(failures)


def test_score_week_is_deterministic_and_bounded(service, worked_examples):
    for ex in worked_examples:
        first, second = _score(service, ex), _score(service, ex)
        assert first == second, ex["case"]
        if first.weakness is not None:
            assert 0.0 <= first.weakness <= 1.0, ex["case"]
        assert 0.0 <= first.confidence <= 1.0 and 0.0 <= first.urgency <= 1.0, ex["case"]


def test_week_score_is_frozen(service):
    score = service.score_week([], [], None)
    with pytest.raises(AttributeError):
        score.status = "weak"


# ── 6. dedup ───────────────────────────────────────────────────────────


def test_is_duplicate_ignores_case_and_punctuation(service):
    assert service.is_duplicate(
        "What is a stateful firewall?", ["what is a STATEFUL firewall", "Define RSA."]
    )


def test_is_duplicate_keeps_unrelated_text(service):
    assert not service.is_duplicate(
        "Explain the key difference between symmetric and asymmetric encryption.",
        ["What is a stateful firewall?"],
    )
    assert not service.is_duplicate("Anything at all", [])

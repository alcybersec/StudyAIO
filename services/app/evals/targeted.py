"""Offline scoring of targeted (weak-spot) generation, and its CI gate.

A case is a synthetic lecture week (the pages of an existing summary case), the
student's weak topics and the stems they already have. A stored fixture is what a
model produced for it (hand-written until a live run replaces it, see
``evals/BASELINE.md``). The fixture is scored **through the same pure rules the
worker task applies** (:func:`app.pipeline.targeted_items.select_items`), so the
gate protects the contract, not the model:

* ``on_topic`` -- the share of kept items that mention a term of a weak topic.
* ``citation_validity`` -- the share of kept items citing a page of the lecture
  whose text supports the topic the item mentions.
* ``dedup`` -- the share of items the duplicate rule classifies as the fixture
  expects (planted duplicates dropped, fresh items kept).
* ``filter_accuracy`` -- the share of items whose whole outcome (kept, uncited,
  duplicate) matches the fixture's ``expect`` label. Reported, not floored.

No AI call, no secrets, the same answer on every run.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.agents.base import FlashcardData, QuizQuestionData
from app.pipeline.targeted_items import select_items
from evals.scoring import _mentions

EVALS_DIR = Path(__file__).resolve().parent
CASES_DIR = EVALS_DIR / "targeted_cases"
FIXTURES_DIR = EVALS_DIR / "targeted_fixtures"
SOURCE_CASES_DIR = EVALS_DIR / "cases"
BASELINE_PATH = EVALS_DIR / "targeted_baseline.json"

#: The bars (M33-S2-AI-021). Citation validity is exact: an item that cites a page
#: the lecture does not have, or a page that does not support it, is a defect.
ON_TOPIC_FLOOR = 0.80
CITATION_FLOOR = 1.0
DEDUP_FLOOR = 0.95
#: How far an aggregate may fall below the baseline before ``--check`` fails.
DEFAULT_THRESHOLD = 0.02


def load_targeted_cases(only: str | None = None) -> list[dict]:
    """Load the targeted case files (sorted), optionally narrowing to one id."""
    cases = [json.loads(p.read_text()) for p in sorted(CASES_DIR.glob("*.json"))]
    if only:
        cases = [c for c in cases if c["id"] == only]
        if not cases:
            raise ValueError(f"No targeted eval case with id {only!r}")
    return cases


def lecture_pages(case: dict) -> dict[int, str]:
    """Page number -> text of the case's source lecture."""
    source = json.loads((SOURCE_CASES_DIR / f"{case['source_case']}.json").read_text())
    return {int(pg.get("page", pg.get("page_number", 0))): pg["text"] for pg in source["pages"]}


def to_items(kind: str, raw: list[dict]) -> list[Any]:
    """Fixture dicts to the adapter's data types (extra keys such as ``expect`` are ignored)."""
    if kind == "quiz":
        return [
            QuizQuestionData(
                question_type=r.get("question_type", "short_answer"),
                question=r.get("question", ""),
                options=r.get("options"),
                correct_answer=r.get("correct_answer", ""),
                explanation=r.get("explanation", ""),
                source_page_ref=r.get("source_page_ref", 1),
            )
            for r in raw
        ]
    return [
        FlashcardData(
            front=r.get("front", ""),
            back=r.get("back", ""),
            tags=r.get("tags", []),
            source_page_ref=r.get("source_page_ref", 1),
        )
        for r in raw
    ]


def _item_text(kind: str, item: Any) -> str:
    if kind == "quiz":
        return f"{item.question} {item.correct_answer} {item.explanation}"
    return f"{item.front} {item.back}"


def _topic_terms(case: dict) -> list[str]:
    return [t for topic in case["weak_topics"] for t in topic["terms"]]


@dataclass
class TargetedScore:
    """One stored generation scored against one case."""

    case_id: str
    kind: str
    total: int
    kept: int
    dropped_uncited: int
    dropped_duplicate: int
    on_topic: float
    citation_validity: float
    dedup: float
    filter_accuracy: float
    problems: list[str] = field(default_factory=list)

    def to_baseline(self) -> dict:
        return {
            "kept": self.kept,
            "dropped_uncited": self.dropped_uncited,
            "dropped_duplicate": self.dropped_duplicate,
            "on_topic": round(self.on_topic, 4),
            "citation_validity": round(self.citation_validity, 4),
            "dedup": round(self.dedup, 4),
            "filter_accuracy": round(self.filter_accuracy, 4),
        }


def score_targeted(case: dict, generated: dict) -> TargetedScore:
    """Score one stored generation. Deterministic, no model.

    Args:
        case: A loaded targeted case.
        generated: The fixture: ``{"kind", "items": [...]}``; each item may carry
            an ``expect`` label (``keep`` | ``uncited`` | ``duplicate``).
    """
    kind = generated.get("kind", case["kind"])
    raw = generated["items"]
    items = to_items(kind, raw)
    pages = lecture_pages(case)
    selection = select_items(kind, items, valid_pages=set(pages), existing=case["existing"])

    terms = _topic_terms(case)
    problems: list[str] = []
    on_topic = cited = 0
    for item in selection.kept:
        text = _item_text(kind, item)
        mentioned = [t for t in terms if _mentions(text, t)]
        if mentioned:
            on_topic += 1
        else:
            problems.append(f"off topic: {text[:60]!r}")
        supported = not mentioned or any(
            _mentions(pages[item.source_page_ref], t) for t in mentioned
        )
        if supported:
            cited += 1
        else:
            problems.append(f"page {item.source_page_ref} does not support: {text[:60]!r}")
    kept = len(selection.kept)

    expected = [r.get("expect") for r in raw]
    labelled = [(o, e) for o, e in zip(selection.outcomes, expected, strict=True) if e]
    wanted = {"keep": "kept", "uncited": "uncited", "duplicate": "duplicate"}
    for outcome, expect in labelled:
        if outcome != wanted[expect]:
            problems.append(f"expected {expect}, filter said {outcome}")
    dedup_pairs = [(o, e) for o, e in labelled if e != "uncited"]
    dedup_right = sum(1 for o, e in dedup_pairs if (o == "duplicate") == (e == "duplicate"))
    return TargetedScore(
        case_id=case["id"],
        kind=kind,
        total=len(items),
        kept=kept,
        dropped_uncited=selection.dropped_uncited,
        dropped_duplicate=selection.dropped_duplicate,
        on_topic=on_topic / kept if kept else 0.0,
        citation_validity=cited / kept if kept else 0.0,
        dedup=dedup_right / len(dedup_pairs) if dedup_pairs else 1.0,
        filter_accuracy=(
            sum(1 for o, e in labelled if o == wanted[e]) / len(labelled) if labelled else 1.0
        ),
        problems=problems,
    )


@dataclass
class TargetedRun:
    """Every case scored from its stored fixture."""

    scores: list[TargetedScore] = field(default_factory=list)
    #: Cases with no fixture file -- a gap, never silently skipped.
    missing_fixtures: list[str] = field(default_factory=list)

    def _mean(self, attr: str) -> float:
        total = len(self.scores) + len(self.missing_fixtures)
        return sum(getattr(s, attr) for s in self.scores) / total if total else 0.0

    @property
    def on_topic(self) -> float:
        return self._mean("on_topic")

    @property
    def citation_validity(self) -> float:
        return self._mean("citation_validity")

    @property
    def dedup(self) -> float:
        return self._mean("dedup")

    @property
    def filter_accuracy(self) -> float:
        return self._mean("filter_accuracy")

    def to_baseline(self, threshold: float = DEFAULT_THRESHOLD, provenance: dict | None = None):
        out: dict[str, Any] = {
            "version": 1,
            "threshold": threshold,
            "aggregate": {
                "cases": len(self.scores),
                "on_topic": round(self.on_topic, 4),
                "citation_validity": round(self.citation_validity, 4),
                "dedup": round(self.dedup, 4),
                "filter_accuracy": round(self.filter_accuracy, 4),
            },
            "cases": {s.case_id: s.to_baseline() for s in self.scores},
        }
        if provenance:
            out["provenance"] = provenance
        return out


def run_targeted_offline(cases: list[dict], fixtures_dir: Path = FIXTURES_DIR) -> TargetedRun:
    """Score each case's stored generation (``<fixtures_dir>/<id>.json``)."""
    run = TargetedRun()
    for case in cases:
        path = fixtures_dir / f"{case['id']}.json"
        if not path.is_file():
            run.missing_fixtures.append(case["id"])
            continue
        run.scores.append(score_targeted(case, json.loads(path.read_text())))
    return run


def load_targeted_baseline(path: Path = BASELINE_PATH) -> dict:
    """Read the committed baseline; a missing file is an error, not a pass."""
    if not path.is_file():
        raise FileNotFoundError(f"baseline not found: {path} (run with --write-baseline)")
    return json.loads(path.read_text())


def check_targeted(run: TargetedRun, baseline: dict, *, expect_all_cases: bool = True) -> list[str]:
    """The CI gate. Returns failures; empty means pass.

    Fails when: a case has no fixture; the baseline and the case set disagree; any
    kept item cites an invalid or unsupporting page; aggregate on-topic is below
    ``ON_TOPIC_FLOOR`` or dedup below ``DEDUP_FLOOR``; or an aggregate has fallen
    more than the threshold below the baseline's.
    """
    failures = [f"{cid}: no stored targeted fixture" for cid in run.missing_fixtures]
    known = baseline.get("cases", {})
    if expect_all_cases:
        seen = {s.case_id for s in run.scores} | set(run.missing_fixtures)
        failures += [
            f"{cid}: in baseline but no such case (stale baseline)"
            for cid in sorted(set(known) - seen)
        ]
    for score in run.scores:
        if score.case_id not in known:
            failures.append(f"{score.case_id}: not in baseline (refresh with --write-baseline)")
        if score.citation_validity < CITATION_FLOOR:
            failures.append(
                f"{score.case_id}: citation validity {score.citation_validity:.2f} "
                f"(must be {CITATION_FLOOR:.1f}): {'; '.join(score.problems)}"
            )
    if run.on_topic < ON_TOPIC_FLOOR:
        failures.append(f"on-topic {run.on_topic:.3f} is below {ON_TOPIC_FLOOR}")
    if run.dedup < DEDUP_FLOOR:
        failures.append(f"dedup {run.dedup:.3f} is below {DEDUP_FLOOR}")

    threshold = float(baseline.get("threshold", DEFAULT_THRESHOLD))
    for name in ("on_topic", "dedup", "filter_accuracy"):
        base = float(baseline["aggregate"][name])
        now = getattr(run, name)
        if now < base - threshold:
            failures.append(
                f"aggregate {name} {now:.3f} is below the baseline {base:.3f} - {threshold}"
            )
    return failures


def format_targeted_report(run: TargetedRun, baseline: dict | None, failures: list[str]) -> str:
    """Human-readable report of a targeted offline run."""
    lines = ["Targeted generation evals (offline, stored fixtures)", ""]
    lines.append(f"{'case':36} {'kind':10} kept  uncited dup  on-topic cite  dedup  filter")
    for s in run.scores:
        lines.append(
            f"{s.case_id:36} {s.kind:10} {s.kept:<5} {s.dropped_uncited:<7} "
            f"{s.dropped_duplicate:<4} {s.on_topic:<8.2f} {s.citation_validity:<5.2f} "
            f"{s.dedup:<6.2f} {s.filter_accuracy:.2f}"
        )
    for cid in run.missing_fixtures:
        lines.append(f"{cid:36} NO FIXTURE")
    lines += [
        "",
        f"aggregate: on-topic {run.on_topic:.3f} (>= {ON_TOPIC_FLOOR}), "
        f"citation validity {run.citation_validity:.3f} (= {CITATION_FLOOR}), "
        f"dedup {run.dedup:.3f} (>= {DEDUP_FLOOR}), filter accuracy {run.filter_accuracy:.3f}",
    ]
    if baseline is not None:
        agg = baseline["aggregate"]
        lines.append(
            f"baseline:  on-topic {agg['on_topic']:.3f}, citation validity "
            f"{agg['citation_validity']:.3f}, dedup {agg['dedup']:.3f}, "
            f"filter accuracy {agg['filter_accuracy']:.3f}"
        )
        lines.append("RESULT: " + ("FAIL" if failures else "PASS"))
        lines += [f"  - {f}" for f in failures]
    return "\n".join(lines)

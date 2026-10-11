"""Offline, deterministic scoring of stored summaries, and the CI regression gate.

The live harness (`evals.runner`) generates summaries through the agent adapter:
it costs money, needs credentials and is not repeatable, so it cannot gate a
merge. This module scores **stored** summaries instead -- one markdown fixture
per case under `evals/fixtures/` -- and compares the result with a committed
baseline. No AI call, no secrets, same answer on every run.

What that gate protects is the *contract*, not the model: the section list is
re-derived from `prompts/summarize.txt` on every run, so a prompt edit that
changes the format breaks the fixtures until an operator refreshes them live;
a scorer change that loosens a check shows up as a baseline mismatch; a case
edit that makes a fixture unfaithful shows up as a faithfulness drop.

Faithfulness here is a proxy that needs no model:

* ``fact_recall`` -- the share of the case's ``required_facts`` the summary
  states. A fact is a set of terms that must co-occur (``all``) or alternatives
  (``any``), so a qualified claim ("average O(1)" *and* "worst case O(n)") is
  not satisfied by half of it.
* ``forbidden_hits`` -- outside-material traps: ``must_not_mention`` terms and
  ``forbidden_claims`` regexes. Each hit halves the score, because an invented
  claim makes a summary unfaithful however complete it is.

``faithfulness = fact_recall * 0.5 ** forbidden_hits``.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from evals.scoring import (
    _mentions,
    check_connections,
    required_sections,
    score_deterministic,
)

EVALS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = EVALS_DIR / "fixtures"
BASELINE_PATH = EVALS_DIR / "baseline.json"

#: How far aggregate faithfulness may fall below the baseline before `--check`
#: fails. Offline scores are exact, so this is slack for deliberate, reviewed
#: case edits rather than for noise.
DEFAULT_THRESHOLD = 0.02

_TITLE = re.compile(r"\A\s*#\s+\S.*Week\s+\d+\s*:\s*\S", re.IGNORECASE)
_FOOTER = re.compile(r"^---\s*\n\s*\*Sources:.*Version:\s*\d+\.?\*\s*\Z", re.MULTILINE | re.DOTALL)
_H2 = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


#: A citation marker as `build_extraction_text` prints it: `[p.3]`, `[D2 p.3]`,
#: and ranges/lists such as `[p.3-5]` or `[p.2, p.4]`.
_CITATION = re.compile(r"\[(?:D\d+\s+)?pp?\.\s*\d+(?:\s*[-–,]\s*(?:p\.\s*)?\d+)*\]")
_MARKER_DOC = re.compile(r"D\d+")
_NUMBER = re.compile(r"\d+")
_KEY_CONCEPTS = re.compile(r"^##\s+Key Concepts\s*$(.*?)(?=^##\s|\Z)", re.MULTILINE | re.DOTALL)
_BULLET = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
_TABLE_RULE = re.compile(r"^[\s:|-]+$")
#: Acronyms and CamelCase names: the shape outside-material imports usually take
#: (QUIC, AVL, MapReduce). Deliberately narrow: plain words are not testable.
_NAMED_TERM = re.compile(r"\b(?:[A-Z]{3,}(?=s?\b)|[A-Z][a-z]+[A-Z][A-Za-z]*\b)")
_MIN_CLAIM_WORDS = 4


def key_concepts_claims(summary: str) -> list[str]:
    """The checkable units of ``## Key Concepts``: bullets, table rows, paragraphs.

    Headings, code fences, table header/rule rows and fragments under four words
    ("Formally:") are not claims.
    """
    match = _KEY_CONCEPTS.search(summary)
    if not match:
        return []
    units: list[str] = []
    para: list[str] = []
    in_code = False
    table_rows = 0

    def flush() -> None:
        if para:
            units.append(" ".join(para))
            para.clear()

    for raw in match.group(1).splitlines():
        line = raw.strip()
        if line.startswith("```"):
            flush()
            in_code = not in_code
            continue
        if in_code:
            continue
        if line.startswith("|"):
            flush()
            table_rows += 1
            # Row 1 is the header and row 2 the rule: neither is a claim.
            if table_rows > 2 and not _TABLE_RULE.match(line):
                units.append(line)
            continue
        table_rows = 0
        if not line or line.startswith("#"):
            flush()
        elif _BULLET.match(line):
            flush()
            units.append(_BULLET.sub("", line))
        else:
            para.append(line.lstrip("> "))
    flush()
    return [u for u in units if len(u.split()) >= _MIN_CLAIM_WORDS]


@dataclass
class CitationReport:
    """How well Key Concepts claims point back at the source (GL#34)."""

    claims: int = 0
    cited: int = 0
    #: Markers naming a page the case does not have.
    invalid_markers: list[str] = field(default_factory=list)
    #: Acronym / CamelCase terms in Key Concepts that the source never mentions.
    ungrounded_terms: list[str] = field(default_factory=list)

    @property
    def coverage(self) -> float:
        """Share of Key Concepts claims carrying a valid marker (1.0 with no claims)."""
        return self.cited / self.claims if self.claims else 1.0


def check_citations(case: dict, summary: str) -> CitationReport:
    """Citation coverage and an outside-material signal for ``## Key Concepts``.

    A claim counts as cited only when every marker in it names a page the case
    has; a marker for page 40 of a 3-page lecture is invented, not a citation.
    Report only: not part of the gate threshold yet.
    """
    pages = case.get("pages", [])
    valid = {int(pg.get("page", pg.get("page_number", 0))) for pg in pages}
    source = "\n".join(pg.get("text", "") for pg in pages)
    claims = key_concepts_claims(summary)
    report = CitationReport(claims=len(claims))
    seen: set[str] = set()
    for claim in claims:
        markers = _CITATION.findall(claim)
        bad = [
            m
            for m in markers
            if any(int(n) not in valid for n in _NUMBER.findall(_MARKER_DOC.sub("", m)))
        ]
        report.invalid_markers += bad
        if markers and not bad:
            report.cited += 1
        for term in _NAMED_TERM.findall(_CITATION.sub("", claim)):
            if term not in seen and not _mentions(source, term):
                seen.add(term)
                report.ungrounded_terms.append(term)
    return report


@dataclass
class OfflineScore:
    """One stored summary scored against one case."""

    case_id: str
    structure_ok: bool
    structure_problems: list[str] = field(default_factory=list)
    coverage: float = 1.0
    fact_recall: float = 1.0
    missing_facts: list[str] = field(default_factory=list)
    forbidden_hits: list[str] = field(default_factory=list)
    connection_violations: list[str] = field(default_factory=list)
    citations: CitationReport = field(default_factory=CitationReport)

    @property
    def faithfulness(self) -> float:
        """``fact_recall`` halved for every outside-material hit."""
        return self.fact_recall * 0.5 ** len(self.forbidden_hits)

    def to_baseline(self) -> dict:
        return {
            "structure_ok": self.structure_ok,
            "coverage": round(self.coverage, 4),
            "fact_recall": round(self.fact_recall, 4),
            "forbidden_hits": len(self.forbidden_hits),
            "faithfulness": round(self.faithfulness, 4),
        }


def check_structure(summary: str) -> list[str]:
    """Problems with a summary's shape against the `summarize.txt` contract.

    Checks the title line, every required ``##`` section present and in the
    prompt's order, and the ``---`` / ``*Sources: ... Version: N.*`` footer.

    Returns:
        One message per problem; empty when the structure is intact.
    """
    problems: list[str] = []
    if not _TITLE.search(summary):
        problems.append("title line '# <Course> — Week <N>: <Topic>' missing")

    wanted = required_sections()
    found = _H2.findall(summary)
    for name in wanted:
        if name not in found:
            problems.append(f"missing section: {name}")
    in_order = [h for h in found if h in wanted]
    expected_order = [h for h in wanted if h in found]
    if in_order != expected_order:
        problems.append("sections out of order")

    if not _FOOTER.search(summary.rstrip() + "\n"):
        problems.append("footer '---' + '*Sources: ... Version: N.*' missing")
    return problems


def _fact_present(fact: dict, summary: str) -> bool:
    all_terms = fact.get("all", [])
    any_terms = fact.get("any", [])
    if not all_terms and not any_terms:
        raise ValueError(f"fact {fact.get('fact')!r} has neither 'all' nor 'any'")
    if any(not _mentions(summary, t) for t in all_terms):
        return False
    return not any_terms or any(_mentions(summary, t) for t in any_terms)


def score_offline(case: dict, summary: str) -> OfflineScore:
    """Score one stored summary. Deterministic, no model.

    Args:
        case: A loaded case file.
        summary: The stored summary markdown.
    """
    base = score_deterministic(case, summary)
    facts = case.get("required_facts", [])
    missing_facts = [f["fact"] for f in facts if not _fact_present(f, summary)]
    fact_recall = (len(facts) - len(missing_facts)) / len(facts) if facts else base.coverage

    hits = list(base.fabricated)
    for claim in case.get("forbidden_claims", []):
        if re.search(claim["pattern"], summary, re.IGNORECASE | re.DOTALL):
            hits.append(claim["claim"])

    problems = check_structure(summary)
    return OfflineScore(
        case_id=case["id"],
        structure_ok=not problems and not base.connection_violations,
        structure_problems=problems + [f"connections: {v}" for v in base.connection_violations],
        coverage=base.coverage,
        fact_recall=fact_recall,
        missing_facts=missing_facts,
        forbidden_hits=hits,
        connection_violations=check_connections(case, summary),
        citations=check_citations(case, summary),
    )


@dataclass
class OfflineRun:
    """Every case scored from its stored fixture."""

    scores: list[OfflineScore] = field(default_factory=list)
    #: Cases with no fixture file -- a gap, never silently skipped.
    missing_fixtures: list[str] = field(default_factory=list)

    @property
    def faithfulness(self) -> float:
        total = len(self.scores) + len(self.missing_fixtures)
        return sum(s.faithfulness for s in self.scores) / total if total else 0.0

    @property
    def coverage(self) -> float:
        total = len(self.scores) + len(self.missing_fixtures)
        return sum(s.coverage for s in self.scores) / total if total else 0.0

    @property
    def citation_coverage(self) -> float:
        """Mean Key Concepts citation coverage (report only, not gated)."""
        total = len(self.scores) + len(self.missing_fixtures)
        return sum(s.citations.coverage for s in self.scores) / total if total else 0.0

    @property
    def structure(self) -> float:
        total = len(self.scores) + len(self.missing_fixtures)
        return sum(1 for s in self.scores if s.structure_ok) / total if total else 0.0

    def to_baseline(
        self, threshold: float = DEFAULT_THRESHOLD, provenance: dict | None = None
    ) -> dict:
        out = {
            "version": 1,
            "threshold": threshold,
            "aggregate": {
                "cases": len(self.scores),
                "faithfulness": round(self.faithfulness, 4),
                "coverage": round(self.coverage, 4),
                "structure": round(self.structure, 4),
            },
            "cases": {s.case_id: s.to_baseline() for s in self.scores},
        }
        if provenance:
            out["provenance"] = provenance
        return out


def run_offline(cases: list[dict], fixtures_dir: Path = FIXTURES_DIR) -> OfflineRun:
    """Score each case's stored summary fixture (``<fixtures_dir>/<id>.md``)."""
    run = OfflineRun()
    for case in cases:
        path = fixtures_dir / f"{case['id']}.md"
        if not path.is_file():
            run.missing_fixtures.append(case["id"])
            continue
        run.scores.append(score_offline(case, path.read_text()))
    return run


def load_baseline(path: Path = BASELINE_PATH) -> dict:
    """Read the committed baseline; a missing file is an error, not a pass."""
    if not path.is_file():
        raise FileNotFoundError(f"baseline not found: {path} (run with --write-baseline)")
    return json.loads(path.read_text())


def known_broken(run: OfflineRun, baseline: dict) -> list[str]:
    """Cases whose structure is broken now *and* was already broken in the baseline."""
    known = baseline.get("cases", {})
    return [
        s.case_id
        for s in run.scores
        if not s.structure_ok
        and s.case_id in known
        and known[s.case_id].get("structure_ok", True) is False
    ]


def check_against_baseline(
    run: OfflineRun, baseline: dict, *, expect_all_cases: bool = True
) -> list[str]:
    """The CI gate (regression semantics). Returns failures; empty means pass.

    Fails when: a case has no fixture; a case is absent from the baseline or
    (with ``expect_all_cases``) a baseline case has no case file (stale
    baseline); a case's structure is broken now but was OK in the baseline; or
    aggregate faithfulness is below ``baseline - threshold``. A structure break
    the baseline already records is a warning (see `known_broken`), not a
    failure, so measured real-model output can be committed as the starting
    point and improved.
    """
    failures: list[str] = []
    for case_id in run.missing_fixtures:
        failures.append(f"{case_id}: no stored summary fixture")

    known = baseline.get("cases", {})
    if expect_all_cases:
        seen = {s.case_id for s in run.scores} | set(run.missing_fixtures)
        for case_id in sorted(set(known) - seen):
            failures.append(f"{case_id}: in baseline but no such case (stale baseline)")
    for score in run.scores:
        entry = known.get(score.case_id)
        if entry is None:
            failures.append(f"{score.case_id}: not in baseline (refresh with --write-baseline)")
        if not score.structure_ok and (entry is None or entry.get("structure_ok", True)):
            failures.append(
                f"{score.case_id}: structure broke (was OK in baseline): "
                f"{'; '.join(score.structure_problems)}"
            )

    threshold = float(baseline.get("threshold", DEFAULT_THRESHOLD))
    floor = float(baseline["aggregate"]["faithfulness"]) - threshold
    if run.faithfulness < floor:
        failures.append(
            f"aggregate faithfulness {run.faithfulness:.3f} is below the floor {floor:.3f}"
            f" (baseline {baseline['aggregate']['faithfulness']:.3f} - threshold {threshold})"
        )
    return failures


def format_offline_report(run: OfflineRun, baseline: dict | None, failures: list[str]) -> str:
    """A short report: one line per case, aggregate, verdict."""
    lines = []
    for s in sorted(run.scores, key=lambda s: s.case_id):
        flag = "ok  " if s.structure_ok and s.faithfulness >= 1.0 else "WARN"
        lines.append(
            f"  [{flag}] {s.case_id:<26} faithfulness {s.faithfulness:.2f}"
            f"  coverage {s.coverage:.0%}  structure {'ok' if s.structure_ok else 'BROKEN'}"
            f"  cited {s.citations.coverage:.0%}"
        )
        for marker in s.citations.invalid_markers:
            lines.append(f"         invalid citation: {marker}")
        for term in s.citations.ungrounded_terms:
            lines.append(f"         term not in source: {term}")
        for fact in s.missing_facts:
            lines.append(f"         missing fact: {fact}")
        for hit in s.forbidden_hits:
            lines.append(f"         forbidden claim: {hit}")
    agg = f"{len(run.scores)} case(s) · faithfulness {run.faithfulness:.3f}"
    agg += f" · coverage {run.coverage:.3f} · structure {run.structure:.0%}"
    agg += f" · citation coverage {run.citation_coverage:.0%} (report only)"
    if baseline:
        agg += f" · baseline {baseline['aggregate']['faithfulness']:.3f}"
    lines += ["", agg]
    if baseline:
        for case_id in known_broken(run, baseline):
            lines.append(f"WARN: {case_id}: structure broken, known at baseline (not a failure)")
    lines.append("RESULT: " + ("FAIL" if failures else "PASS"))
    lines += [f"  - {f}" for f in failures]
    return "\n".join(lines)

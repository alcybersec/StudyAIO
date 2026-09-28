"""Run the summary evals and report.

Drives the **real** `generate_summary` through whichever backend is configured,
so what is measured is the prompt and model actually in use — not a
reimplementation of them that could drift.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from app.agents.base import ExtractionData
from evals.scoring import (
    JUDGE_INSTRUCTION,
    CaseScore,
    parse_judge_reply,
    score_deterministic,
)

logger = structlog.get_logger()

CASES_DIR = Path(__file__).resolve().parent / "cases"


@dataclass
class CaseAggregate:
    """One case run several times.

    A single run is a **sample**, not a verdict: generation is
    non-deterministic, and the first live run of this harness produced four
    fabrications on `normalisation` where a later run produced one. Reporting a
    single draw as a finding invites acting on noise.

    What repetition buys is the distinction between a fabrication that happens
    *every* time — a property of the prompt, worth fixing — and one that happens
    occasionally, which is the model's temperature and may not be worth chasing.
    """

    case_id: str
    runs: list[CaseScore] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.runs)

    @property
    def passed_runs(self) -> int:
        return sum(1 for r in self.runs if r.passed)

    @property
    def passed(self) -> bool:
        """Every run, not most. A case that fails sometimes is not passing."""
        return self.n > 0 and self.passed_runs == self.n

    @property
    def stable(self) -> bool:
        """Whether the runs agreed with each other at all.

        Reported separately because an unstable case means something different
        from a failing one: the number in front of you is not repeatable, and
        comparing it against a previous run tells you nothing.
        """
        return self.passed_runs in (0, self.n)

    @property
    def mean_coverage(self) -> float:
        return sum(r.coverage for r in self.runs) / self.n if self.n else 0.0

    @property
    def fabrication_frequency(self) -> dict[str, int]:
        """Each fabricated term against the number of runs it appeared in."""
        counts: dict[str, int] = {}
        for run in self.runs:
            for term in run.fabricated:
                counts[term] = counts.get(term, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))

    @property
    def persistent_fabrications(self) -> list[str]:
        """Present in every run — a property of the prompt, not the sampling."""
        return [t for t, c in self.fabrication_frequency.items() if c == self.n]

    @property
    def occasional_fabrications(self) -> list[tuple[str, int]]:
        """Present in some runs. Real, but not reliably reproducible."""
        return [(t, c) for t, c in self.fabrication_frequency.items() if c < self.n]

    @property
    def faithfulness_scores(self) -> list[int]:
        return [r.faithfulness for r in self.runs if r.faithfulness is not None]

    @property
    def mean_faithfulness(self) -> float | None:
        scores = self.faithfulness_scores
        return sum(scores) / len(scores) if scores else None

    @property
    def calls(self) -> int:
        return sum(r.calls for r in self.runs)

    @property
    def tokens(self) -> int:
        return sum(r.input_tokens + r.output_tokens for r in self.runs)

    def to_dict(self) -> dict:
        return {
            "case": self.case_id,
            "n": self.n,
            "passed": self.passed,
            "passed_runs": self.passed_runs,
            "stable": self.stable,
            "mean_coverage": round(self.mean_coverage, 3),
            "persistent_fabrications": self.persistent_fabrications,
            "occasional_fabrications": [
                {"term": t, "runs": c} for t, c in self.occasional_fabrications
            ],
            "fabrication_frequency": self.fabrication_frequency,
            "faithfulness": self.faithfulness_scores,
            "mean_faithfulness": (
                round(self.mean_faithfulness, 2) if self.mean_faithfulness else None
            ),
            "calls": self.calls,
            "tokens": self.tokens,
            "runs": [
                {
                    "passed": r.passed,
                    "coverage": round(r.coverage, 3),
                    "missing": r.missing,
                    "fabricated": r.fabricated,
                    "missing_sections": r.missing_sections,
                    "faithfulness": r.faithfulness,
                    "unsupported_claims": r.unsupported_claims,
                    "judge_error": r.judge_error,
                }
                for r in self.runs
            ],
        }


@dataclass
class RunReport:
    """Everything one invocation produced."""

    backend: str
    n: int = 1
    cases: list[CaseAggregate] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.cases if c.passed)

    @property
    def unstable(self) -> list[str]:
        """Cases whose runs disagreed. Their numbers are not comparable."""
        return [c.case_id for c in self.cases if not c.stable]

    @property
    def coverage(self) -> float:
        return sum(c.mean_coverage for c in self.cases) / len(self.cases) if self.cases else 0.0

    @property
    def persistent_fabrications(self) -> int:
        return sum(len(c.persistent_fabrications) for c in self.cases)

    @property
    def total_tokens(self) -> int:
        return sum(c.tokens for c in self.cases)

    @property
    def total_calls(self) -> int:
        return sum(c.calls for c in self.cases)

    def to_dict(self) -> dict:
        return {
            "backend": self.backend,
            "n": self.n,
            "cases": len(self.cases),
            "passed": self.passed,
            "unstable": self.unstable,
            "mean_coverage": round(self.coverage, 3),
            "persistent_fabrications": self.persistent_fabrications,
            "calls": self.total_calls,
            "tokens": self.total_tokens,
            "scores": [c.to_dict() for c in self.cases],
        }


def load_cases(only: str | None = None) -> list[dict]:
    """Load case files, optionally narrowing to one id."""
    cases = [json.loads(p.read_text()) for p in sorted(CASES_DIR.glob("*.json"))]
    if only:
        cases = [c for c in cases if c["id"] == only]
        if not cases:
            raise ValueError(f"No eval case with id {only!r}")
    return cases


async def _judge(agent, case: dict, summary: str, score: CaseScore) -> None:
    """Ask the model whether the summary claims anything the source does not.

    Reuses `answer_question` rather than adding an abstract method every adapter
    would have to implement for one caller. The source and the summary go in as
    context chunks, which is what that method is shaped for.

    A judge failure is recorded on the score and never raised: the deterministic
    findings are worth reporting even when the model half is unavailable.
    """
    source = "\n\n".join(p["text"] for p in case["pages"])
    # The field names are the contract `prompts/answer_question.txt` renders:
    # `chunk.text`, `chunk.course_code`, `chunk.week`, `chunk.page_ref`. An
    # earlier version passed `content`, so every chunk rendered blank and the
    # judge replied that it had been given "empty placeholders" — it graded
    # nothing, three times, and reported it as a parse failure.
    chunks = [
        {
            "text": f"SOURCE MATERIAL (what the lecture actually said):\n{source}",
            "course_code": case.get("course", "EVAL"),
            "week": case.get("week", 0),
            "page_ref": 1,
        },
        {
            "text": f"SUMMARY UNDER REVIEW (grade this):\n{summary}",
            "course_code": case.get("course", "EVAL"),
            "week": case.get("week", 0),
            "page_ref": 2,
        },
    ]
    try:
        result = await agent.answer_question(JUDGE_INSTRUCTION, chunks)
    except Exception as e:  # noqa: BLE001 - reported, never fatal
        score.judge_error = f"{type(e).__name__}: {e}"
        return

    score.faithfulness, score.unsupported_claims, score.judge_error = parse_judge_reply(
        result.answer
    )


async def run(only: str | None = None, judge: bool = True, n: int = 1) -> RunReport:
    """Summarise every case `n` times and score each result.

    Args:
        only: Run a single case id.
        judge: Also ask the model to grade faithfulness. Costs a second call per
            run; the deterministic checks run either way.
        n: Repetitions per case. Generation is non-deterministic, so one run is
            a sample — `n > 1` is what separates a fabrication that happens
            every time from one that happened once.

    Returns:
        The report.
    """
    from app.agents.factory import get_agent
    from app.config import settings

    cases = load_cases(only)
    report = RunReport(backend=settings.agent_backend, n=n)

    for case in cases:
        aggregate = CaseAggregate(case_id=case["id"])

        for attempt in range(n):
            agent = get_agent()
            agent.reset_usage()

            extraction = ExtractionData(
                pages=case["pages"],
                metadata={
                    "course_code": case.get("course", "EVAL"),
                    "week": case.get("week", 1),
                    "title": case.get("title", case["id"]),
                    "filename": f"{case['id']}.pdf",
                },
            )
            result = await agent.generate_summary(extraction, None)
            score = score_deterministic(case, result.content_md)

            if judge:
                await _judge(agent, case, result.content_md, score)

            usage = agent.usage
            score.calls = usage.calls
            score.input_tokens = usage.input_tokens
            score.output_tokens = usage.output_tokens
            aggregate.runs.append(score)

            logger.info(
                "eval_run_scored",
                case=case["id"],
                attempt=attempt + 1,
                of=n,
                passed=score.passed,
                coverage=round(score.coverage, 3),
                fabricated=len(score.fabricated),
            )

        report.cases.append(aggregate)

    return report


def format_report(report: RunReport) -> str:
    """A report meant to be read next to the previous one."""
    suffix = f" (×{report.n})" if report.n > 1 else ""
    lines = [
        f"Backend: {report.backend}{suffix}",
        f"{report.passed}/{len(report.cases)} cases passed"
        f" · mean coverage {report.coverage:.0%}"
        f" · {report.persistent_fabrications} persistent fabrication(s)",
    ]
    if report.unstable:
        # Said loudly: an unstable case means the number is not repeatable, so
        # comparing it against a previous run tells you nothing.
        lines.append(f"UNSTABLE — these did not agree across runs: {', '.join(report.unstable)}")
    lines.append("")

    for c in report.cases:
        mark = "PASS" if c.passed else "FAIL"
        runs = f"{c.passed_runs}/{c.n} runs" if c.n > 1 else ""
        faith = (
            f"faithfulness {c.mean_faithfulness:.1f}/5"
            if c.mean_faithfulness is not None
            else "faithfulness n/a"
        )
        lines.append(
            f"  [{mark}] {c.case_id}  coverage {c.mean_coverage:.0%}  {faith}  {runs}".rstrip()
        )

        missing = sorted({m for r in c.runs for m in r.missing})
        if missing:
            lines.append(f"         missing: {', '.join(missing)}")
        if c.persistent_fabrications:
            # Every run — a property of the prompt, not of sampling.
            lines.append(f"         FABRICATED every run: {', '.join(c.persistent_fabrications)}")
        for term, count in c.occasional_fabrications:
            lines.append(f"         fabricated sometimes: {term} ({count}/{c.n} runs)")
        sections = sorted({s for r in c.runs for s in r.missing_sections})
        if sections:
            lines.append(f"         missing sections: {', '.join(sections)}")
        for claim in dict.fromkeys(cl for r in c.runs for cl in r.unsupported_claims):
            lines.append(f"         unsupported: {claim}")
        errors = {r.judge_error for r in c.runs if r.judge_error}
        for err in errors:
            lines.append(f"         judge unavailable: {err}")

    lines += [
        "",
        f"Cost: {report.total_calls} call(s), {report.total_tokens} token(s)"
        " — 0 tokens means the backend does not report them.",
    ]
    return "\n".join(lines)

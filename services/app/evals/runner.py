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
class RunReport:
    """Everything one run produced."""

    backend: str
    scores: list[CaseScore] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for s in self.scores if s.passed)

    @property
    def coverage(self) -> float:
        return sum(s.coverage for s in self.scores) / len(self.scores) if self.scores else 0.0

    @property
    def fabrications(self) -> int:
        return sum(len(s.fabricated) for s in self.scores)

    @property
    def total_tokens(self) -> int:
        return sum(s.input_tokens + s.output_tokens for s in self.scores)

    @property
    def total_calls(self) -> int:
        return sum(s.calls for s in self.scores)

    def to_dict(self) -> dict:
        return {
            "backend": self.backend,
            "cases": len(self.scores),
            "passed": self.passed,
            "mean_coverage": round(self.coverage, 3),
            "fabrications": self.fabrications,
            "calls": self.total_calls,
            "tokens": self.total_tokens,
            "scores": [
                {
                    "case": s.case_id,
                    "passed": s.passed,
                    "coverage": round(s.coverage, 3),
                    "missing": s.missing,
                    "fabricated": s.fabricated,
                    "missing_sections": s.missing_sections,
                    "faithfulness": s.faithfulness,
                    "unsupported_claims": s.unsupported_claims,
                    "judge_error": s.judge_error,
                    "calls": s.calls,
                    "input_tokens": s.input_tokens,
                    "output_tokens": s.output_tokens,
                }
                for s in self.scores
            ],
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


async def run(only: str | None = None, judge: bool = True) -> RunReport:
    """Summarise every case and score the result.

    Args:
        only: Run a single case id.
        judge: Also ask the model to grade faithfulness. Costs a second call per
            case; the deterministic checks run either way.

    Returns:
        The report.
    """
    from app.agents.factory import get_agent
    from app.config import settings

    cases = load_cases(only)
    report = RunReport(backend=settings.agent_backend)

    for case in cases:
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
        report.scores.append(score)

        logger.info(
            "eval_case_scored",
            case=score.case_id,
            passed=score.passed,
            coverage=round(score.coverage, 3),
            fabricated=len(score.fabricated),
        )

    return report


def format_report(report: RunReport) -> str:
    """A report meant to be read next to the previous one."""
    lines = [
        f"Backend: {report.backend}",
        f"{report.passed}/{len(report.scores)} cases passed"
        f" · mean coverage {report.coverage:.0%}"
        f" · {report.fabrications} fabrication(s)",
        "",
    ]
    for s in report.scores:
        mark = "PASS" if s.passed else "FAIL"
        faith = f"faithfulness {s.faithfulness}/5" if s.faithfulness else "faithfulness n/a"
        lines.append(f"  [{mark}] {s.case_id}  coverage {s.coverage:.0%}  {faith}")
        if s.missing:
            lines.append(f"         missing: {', '.join(s.missing)}")
        if s.fabricated:
            # The finding that matters most: the summary told a student their
            # lecture covered something it never mentioned.
            lines.append(f"         FABRICATED: {', '.join(s.fabricated)}")
        if s.missing_sections:
            lines.append(f"         missing sections: {', '.join(s.missing_sections)}")
        for claim in s.unsupported_claims:
            lines.append(f"         unsupported: {claim}")
        if s.judge_error:
            lines.append(f"         judge unavailable: {s.judge_error}")

    lines += [
        "",
        f"Cost: {report.total_calls} call(s), {report.total_tokens} token(s)"
        " — 0 tokens means the backend does not report them.",
    ]
    return "\n".join(lines)

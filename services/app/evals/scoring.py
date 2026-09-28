"""Scoring a generated summary against a case's expectations.

Three of the four checks are deterministic, free, and need no model. Only
faithfulness needs one, which is why it is optional and reported separately —
an eval you cannot run without credentials is an eval nobody runs.

Nothing here asserts exact generated text. `.claude/rules/tests.md` rules that
out for good reason, and it would be brittle anyway. What is asserted is
whether specific concepts are present or absent, which is stable across runs
even though the prose is not.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

#: Same derivation the golden suite uses: the required sections come from the
#: prompt itself, so editing the prompt cannot leave this checking a stale
#: format. Duplicated here rather than imported from `tests/` — evals are not
#: tests, and an import across that boundary would make each depend on the
#: other's layout.
PROMPT_SECTION_PATTERN = re.compile(r"^\d+\.\s+`##\s+([^`]+)`", re.MULTILINE)

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


def required_sections() -> list[str]:
    """Section titles the summarize prompt promises, in order."""
    return PROMPT_SECTION_PATTERN.findall((PROMPTS_DIR / "summarize.txt").read_text())


def _mentions(haystack: str, needle: str) -> bool:
    """Whether a concept is named, allowing for ordinary prose variation.

    Case-insensitive, and tolerant of the hyphen/space/none spellings that the
    same term attracts (`Boyce-Codd`, `Boyce Codd`). Deliberately *not* fuzzy
    beyond that: a looser match would start reporting coverage that is not
    there, and a coverage number that flatters is worse than none.
    """
    normalise = lambda s: re.sub(r"[\s\-_]+", "", s.casefold())  # noqa: E731
    return normalise(needle) in normalise(haystack)


@dataclass
class CaseScore:
    """How one summary did against one case."""

    case_id: str
    #: Fraction of `must_mention` concepts present, 0.0–1.0.
    coverage: float
    missing: list[str] = field(default_factory=list)
    #: Concepts the source never mentioned but the summary does. Each one is a
    #: claim the student's lecture did not make.
    fabricated: list[str] = field(default_factory=list)
    #: Required sections absent from the output.
    missing_sections: list[str] = field(default_factory=list)
    #: 1–5 from the judge, or None when it was not run.
    faithfulness: int | None = None
    unsupported_claims: list[str] = field(default_factory=list)
    judge_error: str | None = None
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def passed(self) -> bool:
        """The bar: full coverage, nothing fabricated, structure intact.

        Faithfulness is excluded on purpose — it is a model's opinion, and
        gating on it would make the result depend on which backend happened to
        judge. It is reported for reading, not for passing.
        """
        return self.coverage == 1.0 and not self.fabricated and not self.missing_sections


def score_deterministic(case: dict, summary: str) -> CaseScore:
    """Coverage, fabrication and structure. No model, no cost.

    Args:
        case: A loaded case file.
        summary: The generated summary markdown.

    Returns:
        A CaseScore with the model-free fields populated.
    """
    must = case.get("must_mention", [])
    missing = [term for term in must if not _mentions(summary, term)]
    fabricated = [term for term in case.get("must_not_mention", []) if _mentions(summary, term)]
    present_sections = set(re.findall(r"^##\s+(.+?)\s*$", summary, re.MULTILINE))
    missing_sections = [s for s in required_sections() if s not in present_sections]

    return CaseScore(
        case_id=case["id"],
        coverage=(len(must) - len(missing)) / len(must) if must else 1.0,
        missing=missing,
        fabricated=fabricated,
        missing_sections=missing_sections,
    )


JUDGE_INSTRUCTION = """You are grading a lecture summary for FAITHFULNESS to its source.

Faithful means every claim in the summary is supported by the source material.
It does NOT mean complete, well written, or correct in general — a summary can
be accurate about the world and still unfaithful, if it adds something the
lecture did not say.

Mark as unsupported:
- facts, names, dates or figures absent from the source
- techniques or terms the source never introduces
- a qualified claim restated without its qualification (for example, the source
  says "average O(1), worst case O(n)" and the summary says only "O(1)")

Do NOT mark as unsupported:
- rewording, condensing, or reordering
- headings and structure the format requires
- an explicit statement that the lecture contained nothing of some kind

Reply with ONLY a JSON object, no prose and no code fence:
{"faithfulness": <1-5>, "unsupported": ["<claim>", ...]}

5 = every claim supported. 3 = one or two additions that do not mislead.
1 = substantially invented.
"""


def parse_judge_reply(reply: str) -> tuple[int | None, list[str], str | None]:
    """Pull the verdict out of whatever the model actually returned.

    Models wrap JSON in prose or fences however the mood takes them, so this
    takes the first balanced object rather than trusting the whole reply to
    parse. A judge that cannot be parsed is reported as an error rather than
    silently scored zero — an unparseable reply says nothing about the summary.

    Returns:
        (faithfulness, unsupported_claims, error).
    """
    match = re.search(r"\{.*\}", reply, re.DOTALL)
    if not match:
        return None, [], f"no JSON object in judge reply: {reply[:120]!r}"
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        return None, [], f"judge reply was not valid JSON: {e}"

    score = data.get("faithfulness")
    if not isinstance(score, int) or not 1 <= score <= 5:
        return None, [], f"judge returned an out-of-range score: {score!r}"

    unsupported = data.get("unsupported") or []
    if not isinstance(unsupported, list):
        unsupported = [str(unsupported)]
    return score, [str(u) for u in unsupported], None

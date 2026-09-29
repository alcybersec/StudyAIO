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

    Case-insensitive, and tolerant of the hyphen/space/none spellings the same
    term attracts (`Boyce-Codd`, `Boyce Codd`, `BoyceCodd`). Deliberately *not*
    fuzzy beyond that: a looser match reports coverage that is not there, and a
    coverage number that flatters is worse than none.

    **Matches on word boundaries.** The first implementation stripped whitespace
    from both sides and did a plain substring test, which meant a short term
    matched inside longer words: `QUIC` fired on "quickly", and every
    `tcp_congestion` eval run was reported as fabricating QUIC by a summary that
    had merely said slow start "grows the window quickly". Stripping whitespace
    from the *haystack* also let a term match across a word gap, so "the EC
    November deadline" would count as naming `ECN`.

    That cut both ways. A false positive against `must_not_mention` invents a
    fabrication; the same false positive against `must_mention` credits coverage
    the summary never earned, which is the more dangerous direction because it
    flatters silently.
    """
    parts = [re.escape(part) for part in re.split(r"[\s\-_]+", needle.strip()) if part]
    if not parts:
        return False
    # Internal separators stay flexible so "Boyce-Codd" still finds "Boyce Codd".
    # (?<!\w)/(?!\w) rather than \b so terms that start or end with a digit or
    # symbol ("1NF", "O(n)") still anchor correctly.
    pattern = r"[\s\-_]*".join(parts)
    # A trailing English inflection is still the same concept: a lecture that
    # says "rehashing" has named `rehash`. Enumerated rather than "any
    # continuation", because "any" is what let QUIC match "quickly" -- `quic`
    # plus `kly` and `rehash` plus `ing` are structurally identical, and only
    # the suffix list tells them apart.
    return (
        re.search(rf"(?<!\w){pattern}(?:e?s|e?d|ing)?(?!\w)", haystack, re.IGNORECASE) is not None
    )


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


JUDGE_INSTRUCTION = """Grade the SUMMARY UNDER REVIEW for FAITHFULNESS to the SOURCE MATERIAL.

Faithful means every claim in the summary is supported by the source. It does
NOT mean complete, well written, or correct in general — a summary can be
accurate about the world and still unfaithful, if it adds something the lecture
did not say.

Unsupported:
- facts, names, dates or figures absent from the source
- techniques or terms the source never introduces
- a qualified claim restated without its qualification (the source says
  "average O(1), worst case O(n)"; the summary says only "O(1)")

Not unsupported: rewording, condensing, reordering, or required headings.

Reply in the JSON object the format above requires. Put your entire verdict in
the "answer" field and leave "citations" empty. The answer must begin with:

FAITHFULNESS: <1-5>

5 = every claim supported. 3 = one or two additions that do not mislead.
1 = substantially invented.

Then one line per unsupported claim:

UNSUPPORTED: <the claim>

So the whole reply looks like:

{"answer": "FAITHFULNESS: 3\\nUNSUPPORTED: claims BCNF\\nUNSUPPORTED: names OLTP", "citations": []}

No other commentary.
"""

#: `FAITHFULNESS: 4` on its own line.
_SCORE_LINE = re.compile(r"^\s*FAITHFULNESS:\s*([1-5])\b", re.MULTILINE | re.IGNORECASE)
#: `UNSUPPORTED: the claim`, one per line.
_CLAIM_LINE = re.compile(r"^\s*UNSUPPORTED:\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE)


def parse_judge_reply(reply: str) -> tuple[int | None, list[str], str | None]:
    """Pull the verdict out of whatever the model actually returned.

    Line-oriented rather than JSON, because the judge rides on
    `answer_question`, whose adapters parse the model's reply as
    `{"answer": ..., "citations": ...}` and return only the `answer` string. A
    verdict asked for as a bare JSON object was therefore swallowed whole: the
    adapter found no `answer` key and returned `""`, and the harness reported
    "judge unavailable" on every case while still paying for the call.

    A JSON object is still accepted as a fallback, for a backend that returns
    text untouched.

    An unreadable reply is an error, never a zero — a broken judge says nothing
    about the summary, and scoring it 1 would read as a damning verdict.

    Returns:
        (faithfulness, unsupported_claims, error).
    """
    if not reply or not reply.strip():
        return None, [], "judge returned an empty reply"

    match = _SCORE_LINE.search(reply)
    if match:
        claims = [c for c in _CLAIM_LINE.findall(reply) if c.lower() not in {"none", "n/a", "-"}]
        return int(match.group(1)), claims, None

    # Fallback: a raw JSON object, if the backend passed the text through.
    blob = re.search(r"\{.*\}", reply, re.DOTALL)
    if blob:
        try:
            data = json.loads(blob.group(0))
        except json.JSONDecodeError as e:
            return None, [], f"judge reply was not valid JSON: {e}"
        score = data.get("faithfulness")
        if isinstance(score, int) and 1 <= score <= 5:
            unsupported = data.get("unsupported") or []
            if not isinstance(unsupported, list):
                unsupported = [str(unsupported)]
            return score, [str(u) for u in unsupported], None
        return None, [], f"judge returned an out-of-range score: {score!r}"

    return None, [], f"no verdict in judge reply: {reply[:120]!r}"

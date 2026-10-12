"""Pure helpers for chat: scope parsing, quiz intent and source derivation.

No I/O here. ``chat_service`` resolves the parsed course code against the
caller's own courses; nothing in this module touches the database.
"""

import re
from dataclasses import dataclass

# Course codes look like CSCI369 / CSIT302: 3-4 capitals then 3-4 digits.
# Case-sensitive on purpose so "sha256" or "w3c" in prose never match.
_CODE_RE = re.compile(r"\b([A-Z]{3,4})(\d{3,4})\b")
# Technical tokens that share the shape of a course code.
_CODE_STOPLIST = frozenset(
    {"SHA", "AES", "RSA", "RFC", "DES", "UDP", "TLS", "SSL", "EAP", "WPA", "CVE", "MD", "ISO"}
)
_WEEK_RE = re.compile(
    r"\b(?:lectures?|lec|week|wk)\.?\s*#?(\d{1,2})\b|\bw(\d{1,2})\b",
    re.IGNORECASE,
)
MAX_WEEK = 52

_QUIZ_REQUEST_RE = re.compile(
    r"\b(?:create|make|generate|build|write|prepare|draft|produce|give)\b"
    r"(?:\W+\w+){0,6}?\W+"
    r"(?<!unit )(?<!integration )(?:practice\s+)?(?:test|quiz|exam)\b",
    re.IGNORECASE,
)
_QUIZ_ME_RE = re.compile(r"\b(?:quiz|test)\s+me\b", re.IGNORECASE)

_CITE_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
SNIPPET_CHARS = 200


@dataclass(frozen=True)
class ParsedScope:
    """Course code and week named in a message (either may be absent)."""

    code: str | None
    week: int | None


def parse_scope(text: str) -> ParsedScope:
    """Extract a course code and week/lecture number from a message.

    Args:
        text: The user's message.

    Returns:
        ParsedScope; ``code`` is None unless a plausible course code appears,
        ``week`` is None unless a number in 1..52 follows lecture/week/W.
    """
    code: str | None = None
    for m in _CODE_RE.finditer(text):
        if m.group(1) not in _CODE_STOPLIST:
            code = m.group(1) + m.group(2)
            break
    week: int | None = None
    wm = _WEEK_RE.search(text)
    if wm:
        n = int(wm.group(1) or wm.group(2))
        if 1 <= n <= MAX_WEEK:
            week = n
    return ParsedScope(code=code, week=week)


_OVERVIEW_RE = re.compile(
    r"\b(?:summar\w*|overview|recap|outline|key\s+(?:points?|takeaways?)"
    r"|main\s+(?:points?|ideas?|topics?)|cover(?:s|ed)?)\b"
    r"|\bwhat\b[^?.!]*\babout\b"
    r"|\b(?:explain|go\s+over|walk\s+me\s+through)\s+(?:the\s+)?(?:week|lecture|lec|wk)\b",
    re.IGNORECASE,
)


def detect_overview_intent(text: str) -> bool:
    """Return True when the message asks what a lecture/week was about.

    Deliberately conservative: specific questions ("how does ASLR work?")
    do not match. Used only to add the caller's week summary as context.
    """
    return bool(_OVERVIEW_RE.search(text))


def detect_quiz_intent(text: str) -> bool:
    """Return True when the message asks to create a test, quiz or exam.

    Questions about tests ("what is a unit test?") do not match; a creation
    verb or "quiz me" phrasing is required.
    """
    return bool(_QUIZ_REQUEST_RE.search(text) or _QUIZ_ME_RE.search(text))


def build_sources(answer: str, chunks: list[dict]) -> list[dict]:
    """Map every ``[n]`` marker in the answer to the chunk sent at position n.

    Args:
        answer: Assistant answer text containing inline ``[n]`` markers.
        chunks: Chunks in the order they were sent to the model (1-based).

    Returns:
        One source dict per distinct in-range marker, sorted by ref.
    """
    used: set[int] = set()
    for m in _CITE_RE.finditer(answer):
        used.update(int(n) for n in re.split(r"\s*,\s*", m.group(1)))
    sources: list[dict] = []
    for ref in sorted(used):
        if not 1 <= ref <= len(chunks):
            continue
        chunk = chunks[ref - 1]
        sources.append(
            {
                "ref": ref,
                "chunk_id": chunk.get("chunk_id"),
                "text_snippet": (chunk.get("text") or "")[:SNIPPET_CHARS],
                "course_code": chunk.get("course_code"),
                "week": chunk.get("week"),
                "page_ref": chunk.get("page_ref"),
                "artifact_id": chunk.get("artifact_id"),
            }
        )
    return sources

"""Pure rules of targeted generation (ADR 0007 Decision 5), shared with the evals.

No database, no model, no clock: given the same input these functions return the
same output, so the worker task and the offline eval apply exactly the same
citation and dedup rules.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.services.weakspot_service import is_duplicate

#: ADR 0007 Decision 5 prompt-input bounds.
TOPIC_LIMIT = 5
MISSED_LIMIT = 5
AVOID_LIMIT = 30
#: Missed questions look back this far.
MISSED_WINDOW_DAYS = 30
#: ``quiz_questions.focus_topic`` / ``flashcards.focus_topic`` column width.
FOCUS_TOPIC_MAX = 200


@dataclass(frozen=True)
class Attempt:
    """One answer to a question of the unit, as the missed-question scan needs it."""

    question_id: str
    artifact_id: str
    stem: str
    page_ref: int
    is_correct: bool
    created_at: datetime


@dataclass(frozen=True)
class TargetCandidate:
    """A processed artifact of the unit and how many of its questions were missed."""

    artifact_id: str
    created_at: datetime
    missed: int


@dataclass
class Selection:
    """What survived the citation and dedup rules, and what was dropped."""

    kept: list[Any] = field(default_factory=list)
    dropped_uncited: int = 0
    dropped_duplicate: int = 0
    #: One of ``kept`` | ``uncited`` | ``duplicate`` per input item, in input order.
    outcomes: list[str] = field(default_factory=list)


def item_stem(kind: str, item: Any) -> str:
    """The text duplicates are judged on: a question's stem or a card's front."""
    return item.question if kind == "quiz" else item.front


def select_items(
    kind: str, items: list[Any], *, valid_pages: set[int], existing: list[str]
) -> Selection:
    """Apply the citation rule, then the dedup rule, to a model's items.

    An item whose ``source_page_ref`` is not a page of the target extraction is
    dropped as uncited (GL#34: every item cites its slide). Of the rest, an item
    that ``is_duplicate`` of an existing stem or of an earlier kept item is dropped.
    The inputs are not modified.

    Args:
        kind: ``quiz`` or ``flashcards``.
        items: ``QuizQuestionData`` or ``FlashcardData`` from the adapter.
        valid_pages: Page numbers of the target extraction.
        existing: Stems/fronts of the unit's active items.

    Returns:
        The kept items in order, with the two drop counts.
    """
    result = Selection()
    seen = list(existing)
    for item in items:
        page = item.source_page_ref
        if isinstance(page, bool) or not isinstance(page, int) or page not in valid_pages:
            result.dropped_uncited += 1
            result.outcomes.append("uncited")
            continue
        stem = item_stem(kind, item)
        if is_duplicate(stem, seen):
            result.dropped_duplicate += 1
            result.outcomes.append("duplicate")
            continue
        seen.append(stem)
        result.kept.append(item)
        result.outcomes.append("kept")
    return result


def _label(text: str) -> str:
    return " ".join(str(text).split())[:FOCUS_TOPIC_MAX]


def focus_topic_for(kind: str, item: Any, topics: list[str]) -> str | None:
    """The weak topic an item targeted: a naming tag, else a mention, else the first topic.

    Args:
        kind: ``quiz`` or ``flashcards``.
        item: The generated item.
        topics: The generation's topic labels, most important first.

    Returns:
        A label of at most ``FOCUS_TOPIC_MAX`` characters, or None without topics.
    """
    if not topics:
        return None
    if kind == "flashcards":
        tags = {str(t).strip().casefold() for t in (item.tags or [])}
        for topic in topics:
            if topic.casefold() in tags:
                return _label(topic)
    if kind == "quiz":
        text = f"{item.question} {item.correct_answer} {item.explanation}".casefold()
    else:
        text = f"{item.front} {item.back}".casefold()
    for topic in topics:
        if topic.casefold() in text:
            return _label(topic)
    return _label(topics[0])


def build_topics(titles: list[str], concepts: list[str], limit: int = TOPIC_LIMIT) -> list[str]:
    """Slide titles first, then concepts; trimmed, case-insensitively de-duplicated, capped."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in [*titles, *concepts]:
        label = _label(raw)
        key = label.casefold()
        if not label or key in seen:
            continue
        seen.add(key)
        out.append(label)
        if len(out) == limit:
            break
    return out


def latest_missed(attempts: list[Attempt]) -> list[Attempt]:
    """Questions whose most recent attempt was wrong, newest miss first."""
    latest: dict[str, Attempt] = {}
    for attempt in sorted(attempts, key=lambda a: (a.created_at, a.question_id)):
        latest[attempt.question_id] = attempt
    missed = [a for a in latest.values() if not a.is_correct]
    return sorted(missed, key=lambda a: (a.created_at, a.question_id), reverse=True)


def choose_target(candidates: list[TargetCandidate]) -> TargetCandidate | None:
    """Most missed questions; ties by newest ``created_at``, then by id (all descending)."""
    if not candidates:
        return None
    return max(candidates, key=lambda c: (c.missed, c.created_at, c.artifact_id))

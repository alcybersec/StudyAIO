"""Retrieval quality helpers shared by chat and Q&A (relevance floor, follow-ups)."""

import structlog
from prometheus_client import Counter

from app.config import settings

logger = structlog.get_logger()

#: Retrievals that found nothing above the relevance floor, by stage (chat | qa).
#: The only label is that low-cardinality enum (floor 2 label policy).
RETRIEVAL_BELOW_FLOOR = Counter(
    "studyaio_retrieval_below_floor_total",
    "Retrievals answered 'not in your materials' because no chunk cleared the floor.",
    ["stage"],
)

#: Characters of the previous question folded into a follow-up retrieval query.
FOLLOWUP_PREV_CHARS = 300
#: Characters of a week summary passed to the agent as overview context.
SUMMARY_MAX_CHARS = 6000


def filter_by_floor(chunks: list[dict]) -> list[dict]:
    """Keep chunks whose cosine similarity clears ``retrieval_min_similarity``.

    ``search_chunks`` always reports ``similarity``; a chunk dict without the key
    is not a search result and is kept rather than guessed at.
    """
    floor = settings.retrieval_min_similarity
    return [c for c in chunks if c.get("similarity", 1.0) >= floor]


def not_found_reply(code: str | None, week: int | None) -> str:
    """Deterministic reply used when no chunk clears the relevance floor."""
    if code and week is not None:
        scope = f"{code} Week {week}"
    elif code:
        scope = code
    elif week is not None:
        scope = f"Week {week}"
    else:
        scope = "your courses"
    return f"I couldn't find this in your materials for {scope}."


def apply_floor(
    chunks: list[dict],
    *,
    stage: str,
    course_scoped: bool,
    week_scoped: bool,
    scope_code: str | None = None,
    week: int | None = None,
) -> tuple[list[dict], str]:
    """Apply the relevance policy to a scoped search result.

    * course + week scope: no floor. The search was already restricted to that
      week's chunks, so the top-k are relevant by construction; overview
      questions ("what was lecture 2 about?") inherently score low against
      small chunks (GL#35 follow-up).
    * course-only scope: ``retrieval_course_scope_min_similarity``.
    * no scope: ``retrieval_min_similarity``.

    Logs one structured ``retrieval_decision`` event (best similarity, counts,
    decision; never content) and counts below-floor outcomes by stage.

    Returns:
        ``(chunks_to_use, decision)`` where decision is ``bypassed_scoped``,
        ``floor_applied`` (something cleared the floor) or ``below_floor``
        (nothing did; the caller answers with the fixed reply, no AI call).
    """
    best = max((c.get("similarity", 1.0) for c in chunks), default=None)
    if course_scoped and week_scoped:
        kept, decision, floor = list(chunks), "bypassed_scoped", None
    else:
        floor = (
            settings.retrieval_course_scope_min_similarity
            if course_scoped
            else settings.retrieval_min_similarity
        )
        kept = [c for c in chunks if c.get("similarity", 1.0) >= floor]
        decision = "floor_applied" if kept else "below_floor"
    if decision == "below_floor" and chunks:
        RETRIEVAL_BELOW_FLOOR.labels(stage=stage).inc()
    if chunks:
        logger.info(
            "retrieval_decision",
            stage=stage,
            decision=decision,
            best_similarity=best,
            candidates=len(chunks),
            kept=len(kept),
            floor=floor,
            course_scoped=course_scoped,
            week_scoped=week_scoped,
            course_code=scope_code,
            week=week,
        )
    return kept, decision


def with_week_summary(question: str, summary_md: str | None, *, label: str) -> str:
    """Prefix ``question`` with the caller's own week summary as context.

    Args:
        question: The question text sent to the agent.
        summary_md: The summary markdown, or None to leave the question as is.
        label: Human label for the scope, e.g. ``"CSCI369 Week 2"``.
    """
    if not summary_md:
        return question
    body = summary_md[:SUMMARY_MAX_CHARS]
    return f"[Week summary: {label}]\n{body}\n\n[Question]\n{question}"


def build_retrieval_query(
    content: str,
    *,
    code: str | None,
    week: int | None,
    previous_user_message: str | None,
) -> str:
    """Deterministic retrieval query for a chat turn (no AI call).

    The first turn embeds the bare message. A follow-up prepends the carried
    scope and the previous user question so "what about the second one?" is
    embedded with what "one" refers to.
    """
    if previous_user_message is None:
        return content
    parts: list[str] = []
    if code:
        parts.append(f"{code} Week {week}" if week is not None else code)
    elif week is not None:
        parts.append(f"Week {week}")
    parts.append(previous_user_message[:FOLLOWUP_PREV_CHARS])
    parts.append(content)
    return "\n".join(parts)

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


def record_below_floor(
    stage: str, *, searched: int, scope_code: str | None, week: int | None
) -> None:
    """Count and log a below-floor retrieval (no AI call is made)."""
    RETRIEVAL_BELOW_FLOOR.labels(stage=stage).inc()
    logger.info(
        "retrieval_below_floor",
        stage=stage,
        candidates=searched,
        floor=settings.retrieval_min_similarity,
        course_code=scope_code,
        week=week,
    )


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

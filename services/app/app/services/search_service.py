"""Search service — pgvector similarity search and global text search."""

from dataclasses import dataclass, field

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.artifact import LectureArtifact
from app.models.chat_session import ChatSession
from app.models.chunk import Chunk
from app.models.course import Course
from app.models.flashcard import Flashcard
from app.models.summary import Summary

logger = structlog.get_logger()

# Characters that have special meaning in SQL LIKE/ILIKE patterns
_LIKE_ESCAPE_CHAR = "\\"

SNIPPET_LENGTH = 160


@dataclass
class GlobalSearchResult:
    """A single global search match.

    Attributes:
        kind: Entity kind — "course", "course_week", "flashcard", "chat_session".
        title: Display title for the result.
        snippet: Short text excerpt around the match.
        href_meta: Metadata the frontend uses to build the navigation target.
        user_id: Owner user id (tenant isolation marker, not exposed via API).
    """

    kind: str
    title: str
    snippet: str
    href_meta: dict = field(default_factory=dict)
    user_id: str = ""


def escape_like(term: str) -> str:
    """Escape LIKE/ILIKE wildcards so a term matches literally.

    Args:
        term: Raw user-supplied search term.

    Returns:
        Term with backslash, percent, and underscore escaped.
    """
    return (
        term.replace(_LIKE_ESCAPE_CHAR, _LIKE_ESCAPE_CHAR * 2)
        .replace("%", f"{_LIKE_ESCAPE_CHAR}%")
        .replace("_", f"{_LIKE_ESCAPE_CHAR}_")
    )


def _build_snippet(content: str, term: str, length: int = SNIPPET_LENGTH) -> str:
    """Build a short excerpt of `content` centered on the first match of `term`."""
    lowered = content.lower()
    pos = lowered.find(term.lower())
    if pos < 0:
        return content[:length]
    start = max(0, pos - length // 3)
    snippet = content[start : start + length]
    prefix = "…" if start > 0 else ""
    suffix = "…" if start + length < len(content) else ""
    return f"{prefix}{snippet}{suffix}"


async def search_all(
    session: AsyncSession,
    user_id: str,
    query: str,
    limit: int = 10,
) -> list[GlobalSearchResult]:
    """Search courses, week summaries, flashcards, and chat sessions.

    Uses ILIKE with escaped wildcards; per-kind results are capped at `limit`
    and the combined list is trimmed to `limit`. All queries are scoped to
    the given user (tenant isolation).

    Args:
        session: Async database session.
        user_id: Owner user UUID.
        query: Raw search term.
        limit: Maximum number of results overall.

    Returns:
        List of GlobalSearchResult grouped by kind (courses first, then
        week summaries, flashcards, chat sessions).
    """
    pattern = f"%{escape_like(query)}%"
    results: list[GlobalSearchResult] = []

    # 1. Courses — match code or name
    course_rows = await session.execute(
        select(Course.id, Course.code, Course.name)
        .where(
            Course.user_id == user_id,
            Course.code.ilike(pattern, escape=_LIKE_ESCAPE_CHAR)
            | Course.name.ilike(pattern, escape=_LIKE_ESCAPE_CHAR),
        )
        .order_by(Course.code)
        .limit(limit)
    )
    for row in course_rows.all():
        title = f"{row.code} — {row.name}" if row.name else row.code
        results.append(
            GlobalSearchResult(
                kind="course",
                title=title,
                snippet=title,
                href_meta={"course_code": row.code},
                user_id=user_id,
            )
        )

    # 2. Week summaries — match content
    summary_rows = await session.execute(
        select(
            Summary.id,
            Summary.week,
            Summary.content_md,
            Course.code.label("course_code"),
        )
        .join(Course, Summary.course_id == Course.id)
        .where(
            Course.user_id == user_id,
            Summary.content_md.ilike(pattern, escape=_LIKE_ESCAPE_CHAR),
        )
        .order_by(Course.code, Summary.week)
        .limit(limit)
    )
    for row in summary_rows.all():
        results.append(
            GlobalSearchResult(
                kind="course_week",
                title=f"{row.course_code} — Week {row.week}",
                snippet=_build_snippet(row.content_md, query),
                href_meta={
                    "course_code": row.course_code,
                    "week": row.week,
                    "summary_id": row.id,
                },
                user_id=user_id,
            )
        )

    # 3. Flashcards — match front text
    flashcard_rows = await session.execute(
        select(
            Flashcard.id,
            Flashcard.front,
            Flashcard.week,
            Course.code.label("course_code"),
        )
        .join(Course, Flashcard.course_id == Course.id)
        .where(
            Course.user_id == user_id,
            Flashcard.front.ilike(pattern, escape=_LIKE_ESCAPE_CHAR),
        )
        .order_by(Course.code, Flashcard.week)
        .limit(limit)
    )
    for row in flashcard_rows.all():
        results.append(
            GlobalSearchResult(
                kind="flashcard",
                title=_build_snippet(row.front, query, length=80),
                snippet=_build_snippet(row.front, query),
                href_meta={
                    "course_code": row.course_code,
                    "week": row.week,
                    "flashcard_id": row.id,
                },
                user_id=user_id,
            )
        )

    # 4. Chat sessions — match title
    chat_rows = await session.execute(
        select(ChatSession.id, ChatSession.title)
        .where(
            ChatSession.user_id == user_id,
            ChatSession.title.ilike(pattern, escape=_LIKE_ESCAPE_CHAR),
        )
        .order_by(ChatSession.updated_at.desc())
        .limit(limit)
    )
    for row in chat_rows.all():
        results.append(
            GlobalSearchResult(
                kind="chat_session",
                title=row.title,
                snippet=row.title,
                href_meta={"session_id": row.id},
                user_id=user_id,
            )
        )

    trimmed = results[:limit]
    logger.info(
        "global_search_completed",
        query_len=len(query),
        result_count=len(trimmed),
        limit=limit,
    )
    return trimmed


async def search_chunks(
    session: AsyncSession,
    query_embedding: list[float],
    top_k: int | None = None,
    course_id: str | None = None,
    week: int | None = None,
    user_id: str | None = None,
) -> list[dict]:
    """Search for similar chunks using pgvector cosine distance.

    Joins lecture_artifacts for course/week filtering and metadata.

    Args:
        session: Async database session.
        query_embedding: Embedding vector for the query.
        top_k: Maximum results to return (default from settings).
        course_id: Optional course UUID to filter by.
        week: Optional week number to filter by (requires course_id).

    Returns:
        List of dicts with chunk text, metadata, and similarity score.
    """
    k = top_k or settings.search_top_k

    # Build query with cosine distance (<=> operator)
    # Lower distance = more similar; similarity = 1 - distance
    stmt = (
        select(
            Chunk.id,
            Chunk.text,
            Chunk.page_ref,
            Chunk.slide_title,
            Chunk.artifact_id,
            LectureArtifact.week,
            LectureArtifact.title.label("artifact_title"),
            LectureArtifact.original_filename,
            Course.code.label("course_code"),
            Course.id.label("course_id"),
            Chunk.embedding.cosine_distance(query_embedding).label("distance"),
        )
        .join(LectureArtifact, Chunk.artifact_id == LectureArtifact.id)
        .join(Course, LectureArtifact.course_id == Course.id)
        .where(Chunk.embedding.isnot(None))
    )

    # Apply scope filters
    if user_id:
        stmt = stmt.where(LectureArtifact.user_id == user_id)
    if course_id:
        stmt = stmt.where(LectureArtifact.course_id == course_id)
    if week is not None:
        stmt = stmt.where(LectureArtifact.week == week)

    # Order by distance (ascending = most similar first), limit
    stmt = stmt.order_by("distance").limit(k)

    result = await session.execute(stmt)
    rows = result.all()

    logger.info(
        "search_completed",
        result_count=len(rows),
        top_k=k,
        course_id=course_id,
        week=week,
    )

    return [
        {
            "chunk_id": row.id,
            "text": row.text,
            "page_ref": row.page_ref,
            "slide_title": row.slide_title,
            "artifact_id": row.artifact_id,
            "week": row.week,
            "artifact_title": row.artifact_title,
            "original_filename": row.original_filename,
            "course_code": row.course_code,
            "course_id": row.course_id,
            "similarity": round(1.0 - (row.distance or 0.0), 4),
        }
        for row in rows
    ]

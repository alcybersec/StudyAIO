"""Search service — pgvector cosine similarity search with scope filtering."""

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.chunk import Chunk
from app.models.artifact import LectureArtifact
from app.models.course import Course

logger = structlog.get_logger()


async def search_chunks(
    session: AsyncSession,
    query_embedding: list[float],
    top_k: int | None = None,
    course_id: str | None = None,
    week: int | None = None,
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

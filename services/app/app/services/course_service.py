"""Business logic for Course queries."""

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import LectureArtifact
from app.models.course import Course
from app.models.flashcard import Flashcard
from app.models.quiz import QuizQuestion
from app.models.summary import Summary

logger = structlog.get_logger()


async def list_courses(session: AsyncSession) -> list[Course]:
    """Get all courses ordered by code.

    Args:
        session: Database session.

    Returns:
        List of courses ordered alphabetically by code.
    """
    result = await session.execute(
        select(Course).order_by(Course.code)
    )
    return list(result.scalars().all())


async def get_course_by_code(session: AsyncSession, code: str) -> Course | None:
    """Get a course by its code.

    Args:
        session: Database session.
        code: Course code (e.g., "CSIT302").

    Returns:
        Course if found, None otherwise.
    """
    result = await session.execute(
        select(Course).where(Course.code == code)
    )
    return result.scalar_one_or_none()


async def get_course_weeks(session: AsyncSession, course_id: str) -> list[dict]:
    """Get per-week aggregated data for a course.

    Returns a list of dicts with: week, titles (list), artifact_count,
    summary_status, summary_id, flashcard_count, quiz_count.

    Args:
        session: Database session.
        course_id: Course UUID.

    Returns:
        List of per-week summary dicts, ordered by week number.
    """
    # Get artifacts grouped by week
    artifact_rows = await session.execute(
        select(
            LectureArtifact.week,
            func.count(LectureArtifact.id).label("artifact_count"),
            func.array_agg(LectureArtifact.title).label("titles"),
        )
        .where(
            LectureArtifact.course_id == course_id,
            LectureArtifact.week.isnot(None),
        )
        .group_by(LectureArtifact.week)
        .order_by(LectureArtifact.week)
    )
    artifact_data = {
        row.week: {"count": row.artifact_count, "titles": row.titles or []}
        for row in artifact_rows
    }

    # Get summaries for this course
    summary_rows = await session.execute(
        select(Summary.week, Summary.id).where(Summary.course_id == course_id)
    )
    summary_data = {row.week: row.id for row in summary_rows}

    # Get flashcard counts per week
    fc_rows = await session.execute(
        select(
            Flashcard.week,
            func.count(Flashcard.id).label("fc_count"),
        )
        .where(Flashcard.course_id == course_id)
        .group_by(Flashcard.week)
    )
    flashcard_data = {row.week: row.fc_count for row in fc_rows}

    # Get quiz question counts per week
    qq_rows = await session.execute(
        select(
            QuizQuestion.week,
            func.count(QuizQuestion.id).label("qq_count"),
        )
        .where(QuizQuestion.course_id == course_id)
        .group_by(QuizQuestion.week)
    )
    quiz_data = {row.week: row.qq_count for row in qq_rows}

    # Combine all weeks
    all_weeks = sorted(set(artifact_data.keys()) | set(summary_data.keys()))

    result = []
    for week in all_weeks:
        art = artifact_data.get(week, {"count": 0, "titles": []})
        summary_id = summary_data.get(week)
        result.append({
            "week": week,
            "titles": [t for t in art["titles"] if t],
            "artifact_count": art["count"],
            "summary_status": "generated" if summary_id else "pending",
            "summary_id": summary_id,
            "flashcard_count": flashcard_data.get(week, 0),
            "quiz_count": quiz_data.get(week, 0),
        })

    return result

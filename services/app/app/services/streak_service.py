"""Study streak calculation and session recording."""

from datetime import date, datetime, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils import generate_id
from app.models.study_session import StudySession

logger = structlog.get_logger()


async def record_study_session(
    session: AsyncSession,
    course_id: str,
    cards_reviewed: int,
    quiz_questions_answered: int,
    quiz_correct: int,
    duration_seconds: int,
    exam_id: str | None = None,
) -> StudySession:
    """Record or update a study session for today.

    Upserts by (exam_id, course_id, session_date): if a session exists for
    today with the same exam+course, adds to existing totals.

    Args:
        session: Database session.
        course_id: Course UUID.
        cards_reviewed: Number of flashcards reviewed.
        quiz_questions_answered: Number of quiz questions answered.
        quiz_correct: Number of quiz questions answered correctly.
        duration_seconds: Session duration in seconds.
        exam_id: Optional exam UUID.

    Returns:
        Created or updated StudySession.
    """
    today = date.today()

    # Check for existing session today
    query = select(StudySession).where(
        StudySession.course_id == course_id,
        StudySession.session_date == today,
    )
    if exam_id:
        query = query.where(StudySession.exam_id == exam_id)
    else:
        query = query.where(StudySession.exam_id.is_(None))

    result = await session.execute(query)
    existing = result.scalar_one_or_none()

    if existing:
        existing.cards_reviewed += cards_reviewed
        existing.quiz_questions_answered += quiz_questions_answered
        existing.quiz_correct += quiz_correct
        existing.duration_seconds += duration_seconds
        await session.flush()
        logger.info("study_session_updated", session_id=existing.id)
        return existing

    study = StudySession(
        id=generate_id(),
        exam_id=exam_id,
        course_id=course_id,
        session_date=today,
        cards_reviewed=cards_reviewed,
        quiz_questions_answered=quiz_questions_answered,
        quiz_correct=quiz_correct,
        duration_seconds=duration_seconds,
    )
    session.add(study)
    await session.flush()
    logger.info("study_session_created", session_id=study.id)
    return study


async def get_streak(
    session: AsyncSession,
    course_id: str | None = None,
) -> dict:
    """Calculate current and longest study streak.

    A streak is consecutive days with at least one study session.

    Args:
        session: Database session.
        course_id: Optional course filter.

    Returns:
        Dict with current_streak, longest_streak, last_study_date.
    """
    query = (
        select(func.distinct(StudySession.session_date))
        .order_by(StudySession.session_date.desc())
    )
    if course_id:
        query = query.where(StudySession.course_id == course_id)

    result = await session.execute(query)
    dates = [row[0] for row in result.all()]

    if not dates:
        return {"current_streak": 0, "longest_streak": 0, "last_study_date": None}

    last_study = dates[0]
    today = date.today()

    # Calculate longest streak (always needed)
    longest_streak = 1
    current_run = 1
    for i in range(1, len(dates)):
        if dates[i] == dates[i - 1] - timedelta(days=1):
            current_run += 1
            longest_streak = max(longest_streak, current_run)
        else:
            current_run = 1

    # Calculate current streak
    current_streak = 0
    # Start from today, or yesterday if no study today
    if dates[0] == today:
        expected = today
    elif dates[0] == today - timedelta(days=1):
        expected = today - timedelta(days=1)
    else:
        # Last study was more than 1 day ago — current streak is broken
        return {
            "current_streak": 0,
            "longest_streak": longest_streak,
            "last_study_date": last_study.isoformat(),
        }

    for d in dates:
        if d == expected:
            current_streak += 1
            expected -= timedelta(days=1)
        else:
            break

    return {
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "last_study_date": last_study.isoformat(),
    }


async def get_study_history(
    session: AsyncSession,
    exam_id: str | None = None,
    days: int = 30,
) -> list[dict]:
    """Get daily study session aggregates.

    Args:
        session: Database session.
        exam_id: Optional exam filter.
        days: Number of days of history (default 30).

    Returns:
        List of daily aggregate dicts.
    """
    since = date.today() - timedelta(days=days)

    query = (
        select(
            StudySession.session_date,
            func.sum(StudySession.cards_reviewed).label("cards_reviewed"),
            func.sum(StudySession.quiz_questions_answered).label("quiz_answered"),
            func.sum(StudySession.quiz_correct).label("quiz_correct"),
            func.sum(StudySession.duration_seconds).label("duration_seconds"),
            func.count(StudySession.id).label("session_count"),
        )
        .where(StudySession.session_date >= since)
        .group_by(StudySession.session_date)
        .order_by(StudySession.session_date.desc())
    )
    if exam_id:
        query = query.where(StudySession.exam_id == exam_id)

    result = await session.execute(query)
    return [
        {
            "date": row.session_date.isoformat(),
            "cards_reviewed": row.cards_reviewed,
            "quiz_answered": row.quiz_answered,
            "quiz_correct": row.quiz_correct,
            "duration_seconds": row.duration_seconds,
            "session_count": row.session_count,
        }
        for row in result
    ]

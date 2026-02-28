"""Business logic for Flashcard and QuizQuestion management."""

from datetime import datetime

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import FlashcardData, QuizQuestionData
from app.core.utils import generate_id
from app.models.course import Course
from app.models.flashcard import Flashcard
from app.models.quiz import QuizQuestion

logger = structlog.get_logger()


async def save_flashcards(
    session: AsyncSession,
    course_id: str,
    week: int,
    artifact_id: str,
    flashcards: list[FlashcardData],
) -> list[Flashcard]:
    """Save flashcards for an artifact, replacing any existing ones.

    Deletes existing flashcards for this artifact, computes the next
    generation version, and inserts new records.

    Args:
        session: Database session.
        course_id: Course UUID.
        week: Week number.
        artifact_id: Source artifact UUID.
        flashcards: List of FlashcardData from the agent.

    Returns:
        List of created Flashcard records.
    """
    # Delete existing flashcards for this artifact
    await session.execute(
        delete(Flashcard).where(Flashcard.source_artifact_id == artifact_id)
    )

    # Compute next generation version for this course+week
    result = await session.execute(
        select(func.max(Flashcard.generation_version))
        .where(Flashcard.course_id == course_id, Flashcard.week == week)
    )
    max_version = result.scalar() or 0
    next_version = max_version + 1

    records: list[Flashcard] = []
    for fc in flashcards:
        record = Flashcard(
            id=generate_id(),
            course_id=course_id,
            week=week,
            front=fc.front,
            back=fc.back,
            tags=fc.tags,
            source_artifact_id=artifact_id,
            source_page_ref=fc.source_page_ref,
            generation_version=next_version,
        )
        session.add(record)
        records.append(record)

    await session.flush()

    logger.info(
        "flashcards_saved",
        course_id=course_id,
        week=week,
        artifact_id=artifact_id,
        count=len(records),
        version=next_version,
    )
    return records


async def save_quiz_questions(
    session: AsyncSession,
    course_id: str,
    week: int,
    artifact_id: str,
    questions: list[QuizQuestionData],
) -> list[QuizQuestion]:
    """Save quiz questions for an artifact, replacing any existing ones.

    Deletes existing questions for this artifact, computes the next
    generation version, and inserts new records.

    Args:
        session: Database session.
        course_id: Course UUID.
        week: Week number.
        artifact_id: Source artifact UUID.
        questions: List of QuizQuestionData from the agent.

    Returns:
        List of created QuizQuestion records.
    """
    # Delete existing quiz questions for this artifact
    await session.execute(
        delete(QuizQuestion).where(QuizQuestion.source_artifact_id == artifact_id)
    )

    # Compute next generation version for this course+week
    result = await session.execute(
        select(func.max(QuizQuestion.generation_version))
        .where(QuizQuestion.course_id == course_id, QuizQuestion.week == week)
    )
    max_version = result.scalar() or 0
    next_version = max_version + 1

    records: list[QuizQuestion] = []
    for q in questions:
        record = QuizQuestion(
            id=generate_id(),
            course_id=course_id,
            week=week,
            question_type=q.question_type,
            question=q.question,
            options_json=q.options,
            correct_answer=q.correct_answer,
            explanation=q.explanation,
            source_artifact_id=artifact_id,
            source_page_ref=q.source_page_ref,
            generation_version=next_version,
        )
        session.add(record)
        records.append(record)

    await session.flush()

    logger.info(
        "quiz_questions_saved",
        course_id=course_id,
        week=week,
        artifact_id=artifact_id,
        count=len(records),
        version=next_version,
    )
    return records


async def get_flashcards_for_week(
    session: AsyncSession, course_code: str, week: int
) -> list[Flashcard]:
    """Get all flashcards for a specific course week.

    Args:
        session: Database session.
        course_code: Course code (e.g., "CSIT302").
        week: Week number.

    Returns:
        List of Flashcard records ordered by creation time.
    """
    result = await session.execute(
        select(Flashcard)
        .join(Course, Flashcard.course_id == Course.id)
        .where(Course.code == course_code, Flashcard.week == week)
        .order_by(Flashcard.created_at)
    )
    return list(result.scalars().all())


async def get_quiz_questions_for_week(
    session: AsyncSession, course_code: str, week: int
) -> list[QuizQuestion]:
    """Get all quiz questions for a specific course week.

    Args:
        session: Database session.
        course_code: Course code (e.g., "CSIT302").
        week: Week number.

    Returns:
        List of QuizQuestion records ordered by creation time.
    """
    result = await session.execute(
        select(QuizQuestion)
        .join(Course, QuizQuestion.course_id == Course.id)
        .where(Course.code == course_code, QuizQuestion.week == week)
        .order_by(QuizQuestion.created_at)
    )
    return list(result.scalars().all())


async def get_flashcards_for_course(
    session: AsyncSession, course_code: str
) -> list[Flashcard]:
    """Get all flashcards for a course (all weeks).

    Args:
        session: Database session.
        course_code: Course code (e.g., "CSIT302").

    Returns:
        List of Flashcard records ordered by week then creation time.
    """
    result = await session.execute(
        select(Flashcard)
        .join(Course, Flashcard.course_id == Course.id)
        .where(Course.code == course_code)
        .order_by(Flashcard.week, Flashcard.created_at)
    )
    return list(result.scalars().all())


async def get_quiz_questions_for_course(
    session: AsyncSession, course_code: str
) -> list[QuizQuestion]:
    """Get all quiz questions for a course (all weeks).

    Args:
        session: Database session.
        course_code: Course code (e.g., "CSIT302").

    Returns:
        List of QuizQuestion records ordered by week then creation time.
    """
    result = await session.execute(
        select(QuizQuestion)
        .join(Course, QuizQuestion.course_id == Course.id)
        .where(Course.code == course_code)
        .order_by(QuizQuestion.week, QuizQuestion.created_at)
    )
    return list(result.scalars().all())

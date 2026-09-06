"""Business logic for Flashcard and QuizQuestion management."""

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
    await session.execute(delete(Flashcard).where(Flashcard.source_artifact_id == artifact_id))

    # Compute next generation version for this course+week
    result = await session.execute(
        select(func.max(Flashcard.generation_version)).where(
            Flashcard.course_id == course_id, Flashcard.week == week
        )
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
        select(func.max(QuizQuestion.generation_version)).where(
            QuizQuestion.course_id == course_id, QuizQuestion.week == week
        )
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


def _course_scope(*conditions, user_id: str | None):
    """Append the course-owner filter to a set of where() conditions.

    Course codes are unique per user, not globally, so any query that
    resolves a course by code must also pin the owner or it will match
    another user's course of the same code.
    """
    if user_id is not None:
        return (*conditions, Course.user_id == user_id)
    return conditions


async def get_flashcards_for_week(
    session: AsyncSession, course_code: str, week: int, user_id: str | None = None
) -> list[Flashcard]:
    """Get all flashcards for a specific course week.

    Args:
        session: Database session.
        course_code: Course code (e.g., "CSIT302").
        week: Week number.
        user_id: If provided, only match the course owned by this user.
            Course codes are unique *per user* (uq_courses_code_user), so a
            code like "CSIT302" resolves to a different course for every
            user. Endpoints reaching assets by a caller-supplied code MUST
            pass this; omitting it returns every user's assets for that code.

    Returns:
        List of Flashcard records ordered by creation time.
    """
    result = await session.execute(
        select(Flashcard)
        .join(Course, Flashcard.course_id == Course.id)
        .where(*_course_scope(Course.code == course_code, Flashcard.week == week, user_id=user_id))
        .order_by(Flashcard.created_at)
    )
    return list(result.scalars().all())


async def get_quiz_questions_for_week(
    session: AsyncSession, course_code: str, week: int, user_id: str | None = None
) -> list[QuizQuestion]:
    """Get all quiz questions for a specific course week.

    Args:
        session: Database session.
        course_code: Course code (e.g., "CSIT302").
        week: Week number.
        user_id: If provided, only match the course owned by this user.
            Course codes are unique *per user* (uq_courses_code_user), so a
            code like "CSIT302" resolves to a different course for every
            user. Endpoints reaching assets by a caller-supplied code MUST
            pass this; omitting it returns every user's assets for that code.

    Returns:
        List of QuizQuestion records ordered by creation time.
    """
    result = await session.execute(
        select(QuizQuestion)
        .join(Course, QuizQuestion.course_id == Course.id)
        .where(
            *_course_scope(Course.code == course_code, QuizQuestion.week == week, user_id=user_id)
        )
        .order_by(QuizQuestion.created_at)
    )
    return list(result.scalars().all())


async def get_flashcards_for_course(
    session: AsyncSession, course_code: str, user_id: str | None = None
) -> list[Flashcard]:
    """Get all flashcards for a course (all weeks).

    Args:
        session: Database session.
        course_code: Course code (e.g., "CSIT302").
        user_id: If provided, only match the course owned by this user.
            Course codes are unique *per user* (uq_courses_code_user), so a
            code like "CSIT302" resolves to a different course for every
            user. Endpoints reaching assets by a caller-supplied code MUST
            pass this; omitting it returns every user's assets for that code.

    Returns:
        List of Flashcard records ordered by week then creation time.
    """
    result = await session.execute(
        select(Flashcard)
        .join(Course, Flashcard.course_id == Course.id)
        .where(*_course_scope(Course.code == course_code, user_id=user_id))
        .order_by(Flashcard.week, Flashcard.created_at)
    )
    return list(result.scalars().all())


async def get_quiz_questions_for_course(
    session: AsyncSession, course_code: str, user_id: str | None = None
) -> list[QuizQuestion]:
    """Get all quiz questions for a course (all weeks).

    Args:
        session: Database session.
        course_code: Course code (e.g., "CSIT302").
        user_id: If provided, only match the course owned by this user.
            Course codes are unique *per user* (uq_courses_code_user), so a
            code like "CSIT302" resolves to a different course for every
            user. Endpoints reaching assets by a caller-supplied code MUST
            pass this; omitting it returns every user's assets for that code.

    Returns:
        List of QuizQuestion records ordered by week then creation time.
    """
    result = await session.execute(
        select(QuizQuestion)
        .join(Course, QuizQuestion.course_id == Course.id)
        .where(*_course_scope(Course.code == course_code, user_id=user_id))
        .order_by(QuizQuestion.week, QuizQuestion.created_at)
    )
    return list(result.scalars().all())

"""Timed study session planning — budget N minutes across flashcards and quizzes."""

from dataclasses import dataclass

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course
from app.models.quiz import QuizQuestion
from app.services import srs_service

logger = structlog.get_logger()

# Time estimates per item (minutes)
MINUTES_PER_CARD = 2
MINUTES_PER_QUIZ = 3

# Time split
CARD_TIME_FRACTION = 0.6
QUIZ_TIME_FRACTION = 0.4


@dataclass
class TimedSessionPlan:
    """A time-budgeted study session plan."""

    total_minutes: int
    card_ids: list[str]
    quiz_ids: list[str]
    estimated_card_minutes: int
    estimated_quiz_minutes: int
    course_code: str | None
    exam_id: str | None


async def generate_timed_plan(
    session: AsyncSession,
    total_minutes: int,
    course_code: str | None = None,
    exam_id: str | None = None,
) -> TimedSessionPlan:
    """Generate a time-budgeted study plan.

    Args:
        session: Database session.
        total_minutes: Total available study time in minutes (5-180).
        course_code: Optional course code to scope the session.
        exam_id: Optional exam ID to scope to exam's course/weeks.

    Returns:
        TimedSessionPlan with card and quiz IDs.
    """
    # Resolve exam scope if provided
    exam_weeks: list[int] | None = None
    if exam_id:
        from app.models.exam import Exam

        exam_result = await session.execute(select(Exam).where(Exam.id == exam_id))
        exam = exam_result.scalar_one_or_none()
        if exam:
            # Resolve course_code from exam
            course_result = await session.execute(
                select(Course.code).where(Course.id == exam.course_id)
            )
            resolved_code = course_result.scalar_one_or_none()
            if resolved_code:
                course_code = resolved_code
            exam_weeks = exam.weeks_scope

    # Calculate budgets
    card_time = total_minutes * CARD_TIME_FRACTION
    quiz_time = total_minutes * QUIZ_TIME_FRACTION
    card_budget = max(1, int(card_time / MINUTES_PER_CARD))
    quiz_budget = max(1, int(quiz_time / MINUTES_PER_QUIZ))

    # Fetch due flashcards
    cards = await srs_service.get_due_cards(
        session, course_code=course_code, week=None, limit=card_budget
    )

    # If exam_weeks specified, prefer cards from those weeks
    if exam_weeks and cards:
        exam_cards = [c for c in cards if c.week in exam_weeks]
        other_cards = [c for c in cards if c.week not in exam_weeks]
        cards = (exam_cards + other_cards)[:card_budget]

    # Fetch quiz questions
    quiz_query = select(QuizQuestion).join(Course, QuizQuestion.course_id == Course.id)
    if course_code:
        quiz_query = quiz_query.where(Course.code == course_code)
    if exam_weeks:
        quiz_query = quiz_query.where(QuizQuestion.week.in_(exam_weeks))
    quiz_query = quiz_query.order_by(func.random()).limit(quiz_budget)

    quiz_result = await session.execute(quiz_query)
    quizzes = list(quiz_result.scalars().all())

    card_ids = [c.id for c in cards]
    quiz_ids = [q.id for q in quizzes]

    est_card_min = len(card_ids) * MINUTES_PER_CARD
    est_quiz_min = len(quiz_ids) * MINUTES_PER_QUIZ

    logger.info(
        "timed_plan_generated",
        total_minutes=total_minutes,
        cards=len(card_ids),
        quizzes=len(quiz_ids),
        est_total=est_card_min + est_quiz_min,
        course_code=course_code,
        exam_id=exam_id,
    )

    return TimedSessionPlan(
        total_minutes=total_minutes,
        card_ids=card_ids,
        quiz_ids=quiz_ids,
        estimated_card_minutes=est_card_min,
        estimated_quiz_minutes=est_quiz_min,
        course_code=course_code,
        exam_id=exam_id,
    )

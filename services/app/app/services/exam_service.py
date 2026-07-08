"""Business logic for Exam CRUD, quiz attempts, weak topics, and progress."""

from datetime import UTC, datetime

import structlog
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils import generate_id
from app.models.course import Course
from app.models.exam import Exam
from app.models.flashcard import Flashcard
from app.models.flashcard_review import FlashcardReview
from app.models.quiz import QuizQuestion
from app.models.quiz_attempt import QuizAttempt
from app.models.study_session import StudySession
from app.services import readiness_service

logger = structlog.get_logger()


async def create_exam(
    session: AsyncSession,
    course_code: str,
    title: str,
    exam_date: datetime,
    weeks_scope: list[int],
    target_mastery_pct: int = 80,
    user_id: str | None = None,
) -> Exam:
    """Create an exam for a course.

    Args:
        session: Database session.
        course_code: Course code (e.g., "CSIT302").
        title: Exam title.
        exam_date: Exam date/time.
        weeks_scope: List of week numbers covered.
        target_mastery_pct: Target mastery percentage (default 80).

    Returns:
        Created Exam.

    Raises:
        ValueError: If course not found or date is in the past.
    """
    query = select(Course).where(Course.code == course_code)
    if user_id:
        query = query.where(Course.user_id == user_id)
    result = await session.execute(query)
    course = result.scalar_one_or_none()
    if not course:
        raise ValueError(f"Course '{course_code}' not found")

    # Ensure tz-aware for comparison
    aware_exam_date = exam_date if exam_date.tzinfo else exam_date.replace(tzinfo=UTC)
    if aware_exam_date < datetime.now(UTC):
        raise ValueError("Exam date must be in the future")

    exam = Exam(
        id=generate_id(),
        user_id=user_id or course.user_id,
        course_id=course.id,
        title=title,
        exam_date=aware_exam_date,
        weeks_scope=weeks_scope,
        target_mastery_pct=target_mastery_pct,
        status="active",
    )
    session.add(exam)
    await session.flush()

    logger.info("exam_created", exam_id=exam.id, course_code=course_code, title=title)
    return exam


async def get_exam(session: AsyncSession, exam_id: str, user_id: str | None = None) -> Exam | None:
    """Get an exam by ID. Auto-completes if exam_date has passed.

    Args:
        session: Database session.
        exam_id: Exam UUID.
        user_id: If provided, only return exam owned by this user.

    Returns:
        Exam if found, None otherwise.
    """
    query = select(Exam).where(Exam.id == exam_id)
    if user_id is not None:
        query = query.where(Exam.user_id == user_id)
    result = await session.execute(query)
    exam = result.scalar_one_or_none()
    if exam and exam.status == "active" and exam.exam_date < datetime.now(UTC):
        exam.status = "completed"
        await session.flush()
        logger.info("exam_auto_completed", exam_id=exam.id)
    return exam


async def list_exams(
    session: AsyncSession,
    course_code: str | None = None,
    status: str | None = None,
    user_id: str | None = None,
) -> list[Exam]:
    """List exams with optional filters.

    Args:
        session: Database session.
        course_code: Optional course code filter.
        status: Optional status filter (active/completed/archived).

    Returns:
        List of Exam objects ordered by exam_date.
    """
    query = select(Exam).join(Course, Exam.course_id == Course.id)
    if user_id:
        query = query.where(Exam.user_id == user_id)
    if course_code:
        query = query.where(Course.code == course_code)
    if status:
        query = query.where(Exam.status == status)
    query = query.order_by(Exam.exam_date)

    result = await session.execute(query)
    exams = list(result.scalars().all())

    # Auto-complete past active exams
    now = datetime.now(UTC)
    for exam in exams:
        if exam.status == "active" and exam.exam_date < now:
            exam.status = "completed"
    if any(e.status == "completed" for e in exams):
        await session.flush()

    return exams


async def update_exam(
    session: AsyncSession,
    exam_id: str,
    **kwargs,
) -> Exam | None:
    """Update exam fields.

    Args:
        session: Database session.
        exam_id: Exam UUID.
        **kwargs: Fields to update (title, exam_date, weeks_scope, target_mastery_pct).

    Returns:
        Updated Exam or None if not found.
    """
    exam = await get_exam(session, exam_id)
    if not exam:
        return None

    allowed = {"title", "exam_date", "weeks_scope", "target_mastery_pct", "status"}
    for key, value in kwargs.items():
        if key in allowed:
            setattr(exam, key, value)
    exam.updated_at = datetime.now(UTC)
    await session.flush()
    return exam


async def delete_exam(session: AsyncSession, exam_id: str) -> bool:
    """Archive an exam (soft delete).

    Args:
        session: Database session.
        exam_id: Exam UUID.

    Returns:
        True if archived, False if not found.
    """
    exam = await get_exam(session, exam_id)
    if not exam:
        return False
    exam.status = "archived"
    exam.updated_at = datetime.now(UTC)
    await session.flush()
    logger.info("exam_archived", exam_id=exam.id)
    return True


async def record_quiz_attempt(
    session: AsyncSession,
    quiz_question_id: str,
    selected_answer: str,
    is_correct: bool,
    exam_id: str | None = None,
    time_spent_ms: int | None = None,
) -> QuizAttempt:
    """Record an answer to a quiz question.

    Args:
        session: Database session.
        quiz_question_id: Quiz question UUID.
        selected_answer: The answer text.
        is_correct: Whether the answer was correct.
        exam_id: Optional exam to scope this attempt.
        time_spent_ms: Optional time spent in milliseconds.

    Returns:
        Created QuizAttempt.
    """
    attempt = QuizAttempt(
        id=generate_id(),
        quiz_question_id=quiz_question_id,
        exam_id=exam_id,
        selected_answer=selected_answer,
        is_correct=is_correct,
        time_spent_ms=time_spent_ms,
    )
    session.add(attempt)
    await session.flush()
    return attempt


async def get_weak_topics(
    session: AsyncSession,
    course_id: str,
    weeks_scope: list[int],
) -> list[dict]:
    """Identify weak topics by combining quiz accuracy and flashcard ease per week.

    A week is weak if quiz accuracy <70% OR average flashcard ease <2.0.
    Sorted weakest-first.

    Args:
        session: Database session.
        course_id: Course UUID.
        weeks_scope: List of week numbers to analyze.

    Returns:
        List of dicts with week, quiz_accuracy, avg_ease, reason.
    """
    quiz_by_week, ease_by_week = await readiness_service.collect_week_stats(
        session, course_id, weeks_scope
    )

    weak = []
    for week in weeks_scope:
        quiz = quiz_by_week.get(week, {"attempts": 0, "accuracy": None})
        avg_ease = ease_by_week.get(week)

        reasons, weakness_score = readiness_service.score_week(quiz["accuracy"], avg_ease)

        if reasons:
            weak.append(
                {
                    "week": week,
                    "quiz_accuracy": round(quiz["accuracy"], 1)
                    if quiz["accuracy"] is not None
                    else None,
                    "quiz_attempts": quiz["attempts"],
                    "avg_ease": round(avg_ease, 2) if avg_ease is not None else None,
                    "reasons": reasons,
                    "weakness_score": round(weakness_score, 1),
                }
            )

    weak.sort(key=lambda x: x["weakness_score"], reverse=True)
    return weak


async def get_exam_progress(
    session: AsyncSession,
    exam_id: str,
) -> dict | None:
    """Get comprehensive exam progress data.

    Args:
        session: Database session.
        exam_id: Exam UUID.

    Returns:
        Dict with progress data or None if exam not found.
    """
    exam = await get_exam(session, exam_id)
    if not exam:
        return None

    now = datetime.now(UTC)
    days_remaining = max(0, (exam.exam_date - now).days)

    # Quiz accuracy across exam scope
    quiz_result = await session.execute(
        select(
            func.count(QuizAttempt.id).label("total"),
            func.sum(case((QuizAttempt.is_correct == True, 1), else_=0)).label("correct"),  # noqa: E712
        )
        .join(QuizQuestion, QuizAttempt.quiz_question_id == QuizQuestion.id)
        .where(
            QuizQuestion.course_id == exam.course_id,
            QuizQuestion.week.in_(exam.weeks_scope),
        )
    )
    quiz_row = quiz_result.one()
    quiz_total = quiz_row.total or 0
    quiz_correct = quiz_row.correct or 0
    quiz_accuracy = round(quiz_correct / quiz_total * 100, 1) if quiz_total > 0 else 0

    # Flashcard mastery in scope
    fc_result = await session.execute(
        select(
            func.count(Flashcard.id).label("total"),
        ).where(
            Flashcard.course_id == exam.course_id,
            Flashcard.week.in_(exam.weeks_scope),
        )
    )
    fc_total = fc_result.scalar() or 0

    mastered_result = await session.execute(
        select(func.count(FlashcardReview.id))
        .join(Flashcard, FlashcardReview.flashcard_id == Flashcard.id)
        .where(
            Flashcard.course_id == exam.course_id,
            Flashcard.week.in_(exam.weeks_scope),
            FlashcardReview.interval_days > 21,
        )
    )
    fc_mastered = mastered_result.scalar() or 0
    mastery_pct = round(fc_mastered / fc_total * 100, 1) if fc_total > 0 else 0

    # Session count
    session_count_result = await session.execute(
        select(func.count(StudySession.id)).where(StudySession.exam_id == exam_id)
    )
    session_count = session_count_result.scalar() or 0

    # Weak topics
    weak_topics = await get_weak_topics(session, exam.course_id, exam.weeks_scope)
    weak_weeks = [w["week"] for w in weak_topics]

    return {
        "exam_id": exam.id,
        "title": exam.title,
        "course_id": exam.course_id,
        "exam_date": exam.exam_date.isoformat(),
        "status": exam.status,
        "days_remaining": days_remaining,
        "mastery_pct": mastery_pct,
        "target_mastery_pct": exam.target_mastery_pct,
        "quiz_accuracy": quiz_accuracy,
        "quiz_total": quiz_total,
        "quiz_correct": quiz_correct,
        "flashcard_total": fc_total,
        "flashcard_mastered": fc_mastered,
        "weak_weeks": weak_weeks,
        "session_count": session_count,
        "weeks_scope": exam.weeks_scope,
    }

"""Shared exam-readiness scoring — weak-topic math and per-topic detail.

The per-week weakness scoring here is the single source of truth; both
`exam_service.get_weak_topics` and the readiness drill-down endpoint use it.
"""

import structlog
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import LectureArtifact
from app.models.flashcard import Flashcard
from app.models.flashcard_review import FlashcardReview
from app.models.quiz import QuizQuestion
from app.models.quiz_attempt import QuizAttempt

logger = structlog.get_logger()

# Thresholds for weak-topic detection (pinned to the original inline math)
WEAK_QUIZ_ACCURACY_THRESHOLD = 70.0
WEAK_EASE_THRESHOLD = 2.0
EASE_WEAKNESS_MULTIPLIER = 50.0
UNSTUDIED_WEAKNESS_SCORE = 100.0


def score_week(
    quiz_accuracy: float | None,
    avg_ease: float | None,
) -> tuple[list[str], float]:
    """Score a single week's weakness from quiz accuracy and flashcard ease.

    A week is weak if quiz accuracy < 70% or average ease < 2.0. Weeks with
    no data at all are "unstudied" and score 100.

    Args:
        quiz_accuracy: Quiz accuracy percentage (0-100) or None if no attempts.
        avg_ease: Average flashcard ease factor or None if no reviews.

    Returns:
        Tuple of (reasons, weakness_score).
    """
    reasons: list[str] = []
    weakness_score = 0.0

    if quiz_accuracy is not None and quiz_accuracy < WEAK_QUIZ_ACCURACY_THRESHOLD:
        reasons.append("low_quiz_accuracy")
        weakness_score += WEAK_QUIZ_ACCURACY_THRESHOLD - quiz_accuracy

    if avg_ease is not None and avg_ease < WEAK_EASE_THRESHOLD:
        reasons.append("low_flashcard_ease")
        weakness_score += (WEAK_EASE_THRESHOLD - avg_ease) * EASE_WEAKNESS_MULTIPLIER

    if quiz_accuracy is None and avg_ease is None:
        reasons.append("unstudied")
        weakness_score += UNSTUDIED_WEAKNESS_SCORE

    return reasons, weakness_score


async def collect_week_stats(
    session: AsyncSession,
    course_id: str,
    weeks_scope: list[int],
) -> tuple[dict[int, dict], dict[int, float]]:
    """Collect per-week quiz accuracy and flashcard ease for a course scope.

    Args:
        session: Database session.
        course_id: Course UUID.
        weeks_scope: Week numbers to analyze.

    Returns:
        Tuple of (quiz_by_week, ease_by_week). quiz_by_week maps week to
        {"attempts": int, "accuracy": float | None}; ease_by_week maps week
        to average ease factor.
    """
    quiz_stats = await session.execute(
        select(
            QuizQuestion.week,
            func.count(QuizAttempt.id).label("attempts"),
            func.sum(case((QuizAttempt.is_correct == True, 1), else_=0)).label("correct"),  # noqa: E712
        )
        .join(QuizAttempt, QuizQuestion.id == QuizAttempt.quiz_question_id)
        .where(
            QuizQuestion.course_id == course_id,
            QuizQuestion.week.in_(weeks_scope),
        )
        .group_by(QuizQuestion.week)
    )
    quiz_by_week: dict[int, dict] = {}
    for row in quiz_stats:
        accuracy = (row.correct / row.attempts * 100) if row.attempts > 0 else None
        quiz_by_week[row.week] = {"attempts": row.attempts, "accuracy": accuracy}

    ease_stats = await session.execute(
        select(
            Flashcard.week,
            func.avg(FlashcardReview.ease_factor).label("avg_ease"),
        )
        .join(FlashcardReview, Flashcard.id == FlashcardReview.flashcard_id)
        .where(
            Flashcard.course_id == course_id,
            Flashcard.week.in_(weeks_scope),
        )
        .group_by(Flashcard.week)
    )
    ease_by_week = {row.week: row.avg_ease for row in ease_stats}

    return quiz_by_week, ease_by_week


async def compute_readiness_detail(
    session: AsyncSession,
    exam_id: str,
    user_id: str,
) -> dict | None:
    """Compute topic-level readiness detail for an exam.

    Uses the same weak-topic math as `exam_service.get_weak_topics` and the
    overall readiness score from analytics.

    Args:
        session: Database session.
        exam_id: Exam UUID.
        user_id: Requesting user UUID (tenant isolation).

    Returns:
        Dict {exam_id, title, overall, topics: [{topic, week, accuracy,
        weight, card_count}]}, or None if the exam is not found for this user.
    """
    from app.services import analytics_service, exam_service

    exam = await exam_service.get_exam(session, exam_id, user_id=user_id)
    if not exam:
        return None

    readiness = await analytics_service.get_exam_readiness(session, exam_id, user_id)
    overall = int(round(readiness["readiness_score"])) if readiness else 0

    weeks_scope = list(exam.weeks_scope or [])
    quiz_by_week, ease_by_week = await collect_week_stats(session, exam.course_id, weeks_scope)

    # Flashcard counts per week
    card_rows = await session.execute(
        select(
            Flashcard.week,
            func.count(Flashcard.id).label("card_count"),
        )
        .where(
            Flashcard.course_id == exam.course_id,
            Flashcard.week.in_(weeks_scope),
        )
        .group_by(Flashcard.week)
    )
    cards_by_week = {row.week: row.card_count for row in card_rows}

    # Topic names from artifact titles (first non-null per week)
    title_rows = await session.execute(
        select(LectureArtifact.week, LectureArtifact.title)
        .where(
            LectureArtifact.course_id == exam.course_id,
            LectureArtifact.week.in_(weeks_scope),
            LectureArtifact.title.isnot(None),
        )
        .order_by(LectureArtifact.week, LectureArtifact.created_at)
    )
    title_by_week: dict[int, str] = {}
    for row in title_rows:
        title_by_week.setdefault(row.week, row.title)

    topics = []
    for week in weeks_scope:
        quiz = quiz_by_week.get(week, {"attempts": 0, "accuracy": None})
        avg_ease = ease_by_week.get(week)
        _, weakness_score = score_week(quiz["accuracy"], avg_ease)

        topics.append(
            {
                "topic": title_by_week.get(week, f"Week {week}"),
                "week": week,
                "accuracy": round(quiz["accuracy"], 1) if quiz["accuracy"] is not None else None,
                "weight": round(weakness_score, 1),
                "card_count": cards_by_week.get(week, 0),
            }
        )

    logger.info("readiness_detail_computed", exam_id=exam_id, topic_count=len(topics))

    return {
        "exam_id": exam.id,
        "title": exam.title,
        "overall": overall,
        "topics": topics,
    }

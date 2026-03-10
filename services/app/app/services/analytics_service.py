"""Learning analytics service — aggregation queries and snapshot management."""

from collections import defaultdict
from datetime import date, timedelta

import structlog
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils import generate_id
from app.models.analytics_snapshot import AnalyticsSnapshot
from app.models.course import Course
from app.models.flashcard import Flashcard
from app.models.flashcard_review import FlashcardReview
from app.models.study_session import StudySession

logger = structlog.get_logger()


async def get_overview(session: AsyncSession, user_id: str) -> dict:
    """Get overview stats: total study hours, mastery %, streak info, cards reviewed.

    Returns dict with: total_study_hours, total_cards_reviewed, total_sessions,
    mastery_pct (% of flashcards with interval > 21 days), active_courses.

    Args:
        session: Database session.
        user_id: User UUID.

    Returns:
        Dict with aggregated overview metrics.
    """
    # Total study time from study_sessions
    time_result = await session.execute(
        select(
            func.coalesce(func.sum(StudySession.duration_seconds), 0),
            func.coalesce(func.sum(StudySession.cards_reviewed), 0),
            func.count(StudySession.id),
        ).where(StudySession.user_id == user_id)
    )
    row = time_result.one()
    total_seconds = row[0]
    total_cards = row[1]
    total_sessions = row[2]

    # Mastery: flashcards with interval > 21 / total flashcards (user-scoped via Course)
    total_fc_result = await session.execute(
        select(func.count(Flashcard.id))
        .join(Course, Flashcard.course_id == Course.id)
        .where(Course.user_id == user_id)
    )
    total_fc = total_fc_result.scalar() or 0

    mastered_result = await session.execute(
        select(func.count(FlashcardReview.id))
        .join(Flashcard, FlashcardReview.flashcard_id == Flashcard.id)
        .join(Course, Flashcard.course_id == Course.id)
        .where(Course.user_id == user_id, FlashcardReview.interval_days > 21)
    )
    mastered = mastered_result.scalar() or 0
    mastery_pct = round(mastered / total_fc * 100, 1) if total_fc > 0 else 0.0

    # Active courses count
    active_courses_result = await session.execute(
        select(func.count(func.distinct(Course.id))).where(Course.user_id == user_id)
    )
    active_courses = active_courses_result.scalar() or 0

    return {
        "total_study_hours": round(total_seconds / 3600, 1),
        "total_cards_reviewed": total_cards,
        "total_sessions": total_sessions,
        "mastery_pct": mastery_pct,
        "total_flashcards": total_fc,
        "mastered_flashcards": mastered,
        "active_courses": active_courses,
    }


async def get_study_heatmap(session: AsyncSession, user_id: str, days: int = 90) -> list[dict]:
    """Get daily study totals for heatmap display.

    Returns list of {date: "YYYY-MM-DD", minutes: float, cards: int, sessions: int}
    for each day in the range, including zero-activity days.

    Args:
        session: Database session.
        user_id: User UUID.
        days: Number of days to look back (default 90).

    Returns:
        List of daily study activity dicts.
    """
    since = date.today() - timedelta(days=days)

    result = await session.execute(
        select(
            StudySession.session_date,
            func.sum(StudySession.duration_seconds).label("total_seconds"),
            func.sum(StudySession.cards_reviewed).label("total_cards"),
            func.count(StudySession.id).label("session_count"),
        )
        .where(StudySession.user_id == user_id, StudySession.session_date >= since)
        .group_by(StudySession.session_date)
        .order_by(StudySession.session_date)
    )

    # Build a dict of actual data
    data_by_date: dict[date, dict] = {}
    for row in result:
        data_by_date[row.session_date] = {
            "date": row.session_date.isoformat(),
            "minutes": round(row.total_seconds / 60, 1),
            "cards": row.total_cards,
            "sessions": row.session_count,
        }

    # Fill in all days in range (including zero days)
    heatmap: list[dict] = []
    current = since
    today = date.today()
    while current <= today:
        if current in data_by_date:
            heatmap.append(data_by_date[current])
        else:
            heatmap.append(
                {
                    "date": current.isoformat(),
                    "minutes": 0,
                    "cards": 0,
                    "sessions": 0,
                }
            )
        current += timedelta(days=1)

    return heatmap


async def get_retention_data(
    session: AsyncSession, user_id: str, course_code: str | None = None
) -> list[dict]:
    """Get retention curve data — average retention at each interval bucket.

    Groups flashcard reviews by interval_days buckets (1, 3, 7, 14, 21, 30, 60, 90+)
    and calculates what fraction of cards at that interval still have ease >= 2.0.

    Args:
        session: Database session.
        user_id: User UUID.
        course_code: Optional course code filter.

    Returns:
        List of {interval_bucket: int, retention_pct: float, card_count: int}.
    """
    query = (
        select(
            FlashcardReview.interval_days,
            FlashcardReview.ease_factor,
            Course.code,
        )
        .join(Flashcard, FlashcardReview.flashcard_id == Flashcard.id)
        .join(Course, Flashcard.course_id == Course.id)
        .where(Course.user_id == user_id)
    )
    if course_code:
        query = query.where(Course.code == course_code)

    result = await session.execute(query)
    rows = result.all()

    if not rows:
        return []

    # Define buckets
    buckets = [1, 3, 7, 14, 21, 30, 60, 90]

    def get_bucket(interval: int) -> int:
        """Map an interval to its nearest bucket."""
        for b in buckets:
            if interval <= b:
                return b
        return 90

    # Group by bucket
    bucket_data: dict[int, dict[str, int]] = defaultdict(lambda: {"total": 0, "retained": 0})

    for interval, ease, _code in rows:
        b = get_bucket(interval)
        bucket_data[b]["total"] += 1
        # Consider retained if ease >= 2.0 (not struggling)
        if ease >= 2.0:
            bucket_data[b]["retained"] += 1

    return [
        {
            "interval_bucket": b,
            "retention_pct": round(bucket_data[b]["retained"] / bucket_data[b]["total"] * 100, 1)
            if bucket_data[b]["total"] > 0
            else 0,
            "card_count": bucket_data[b]["total"],
        }
        for b in sorted(bucket_data.keys())
    ]


async def get_mastery_breakdown(
    session: AsyncSession, user_id: str, course_code: str | None = None
) -> list[dict]:
    """Get per-week mastery breakdown.

    For each course+week combination, calculates:
    - total flashcards
    - mastered (interval > 21)
    - learning (has review, interval <= 21)
    - new (no review)
    - mastery_pct

    Args:
        session: Database session.
        user_id: User UUID.
        course_code: Optional course code filter.

    Returns:
        List of {course_code, week, total, mastered, learning, new, mastery_pct}.
    """
    query = (
        select(
            Course.code,
            Flashcard.week,
            func.count(Flashcard.id).label("total"),
            func.sum(
                case(
                    (FlashcardReview.interval_days > 21, 1),
                    else_=0,
                )
            ).label("mastered"),
            func.sum(
                case(
                    (
                        (FlashcardReview.id.isnot(None)) & (FlashcardReview.interval_days <= 21),
                        1,
                    ),
                    else_=0,
                )
            ).label("learning"),
        )
        .join(Course, Flashcard.course_id == Course.id)
        .outerjoin(FlashcardReview, Flashcard.id == FlashcardReview.flashcard_id)
        .where(Course.user_id == user_id)
    )
    if course_code:
        query = query.where(Course.code == course_code)

    query = query.group_by(Course.code, Flashcard.week).order_by(Course.code, Flashcard.week)

    result = await session.execute(query)

    return [
        {
            "course_code": row.code,
            "week": row.week,
            "total": row.total,
            "mastered": row.mastered or 0,
            "learning": row.learning or 0,
            "new": row.total - (row.mastered or 0) - (row.learning or 0),
            "mastery_pct": round((row.mastered or 0) / row.total * 100, 1) if row.total > 0 else 0,
        }
        for row in result
    ]


async def get_exam_readiness(session: AsyncSession, exam_id: str, user_id: str) -> dict | None:
    """Get exam readiness score — weighted combination of mastery, quiz accuracy, and study consistency.

    Weights: mastery 40%, quiz accuracy 30%, study consistency 30%.

    Args:
        session: Database session.
        exam_id: Exam UUID.
        user_id: User UUID.

    Returns:
        Dict with readiness_score (0-100), component scores, and details,
        or None if exam not found.
    """
    from app.services.exam_service import get_exam, get_exam_progress, get_weak_topics

    exam = await get_exam(session, exam_id, user_id=user_id)
    if not exam:
        return None

    progress = await get_exam_progress(session, exam_id)
    if not progress:
        return None

    # Component 1: Mastery (40%)
    mastery_score = progress["mastery_pct"]

    # Component 2: Quiz accuracy (30%)
    quiz_score = progress["quiz_accuracy"]

    # Component 3: Study consistency (30%) — sessions in last 7 days / 7
    week_ago = date.today() - timedelta(days=7)
    consistency_result = await session.execute(
        select(func.count(func.distinct(StudySession.session_date))).where(
            StudySession.user_id == user_id,
            StudySession.session_date >= week_ago,
        )
    )
    study_days = consistency_result.scalar() or 0
    consistency_score = min(100, round(study_days / 7 * 100, 1))

    readiness_score = round(mastery_score * 0.4 + quiz_score * 0.3 + consistency_score * 0.3, 1)

    weak_topics = await get_weak_topics(session, exam.course_id, exam.weeks_scope)

    return {
        "exam_id": exam.id,
        "title": exam.title,
        "readiness_score": readiness_score,
        "mastery_score": mastery_score,
        "quiz_score": quiz_score,
        "consistency_score": consistency_score,
        "days_remaining": progress["days_remaining"],
        "weak_weeks": [w["week"] for w in weak_topics[:5]],
        "flashcard_total": progress["flashcard_total"],
        "flashcard_mastered": progress["flashcard_mastered"],
        "quiz_total": progress["quiz_total"],
        "quiz_correct": progress["quiz_correct"],
        "study_days_last_week": study_days,
    }


async def compute_and_store_snapshot(session: AsyncSession, user_id: str) -> AnalyticsSnapshot:
    """Compute and store a daily analytics snapshot.

    If a snapshot already exists for today, updates it. Otherwise creates a new one.

    Args:
        session: Database session.
        user_id: User UUID.

    Returns:
        The created or updated AnalyticsSnapshot.
    """
    today = date.today()

    # Get overview as the snapshot metrics
    overview = await get_overview(session, user_id)

    # Check for existing snapshot
    result = await session.execute(
        select(AnalyticsSnapshot).where(
            AnalyticsSnapshot.user_id == user_id,
            AnalyticsSnapshot.snapshot_date == today,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.metrics_json = overview
        await session.flush()
        logger.info("analytics_snapshot_updated", user_id=user_id, date=today.isoformat())
        return existing

    snapshot = AnalyticsSnapshot(
        id=generate_id(),
        user_id=user_id,
        snapshot_date=today,
        metrics_json=overview,
    )
    session.add(snapshot)
    await session.flush()
    logger.info("analytics_snapshot_created", user_id=user_id, date=today.isoformat())
    return snapshot

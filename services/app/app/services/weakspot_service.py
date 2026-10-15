"""Weak-spot engine (ADR 0007): per-week weakness scores, "Study tonight", targeted requests.

The unit of weakness is ``(user, course, week)``. Scores are a deterministic function of
quiz answers, spaced-repetition state and exam dates, derived on every read; the only
stored outputs are a frozen daily ``StudyPlan`` and the ``TargetedGeneration`` job rows.
Nothing here calls an AI provider: generation runs in the worker, and this module only
records the request.

Every function that touches user data takes ``user_id`` as a required keyword and every
query is joined to ``courses.user_id`` (floor 1).
"""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

import structlog
from prometheus_client import Counter, Histogram
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import user_now, user_today, utc_now
from app.core.exceptions import (
    GlobalCeilingError,
    QuotaExceededError,
    TargetedDailyCapError,
    TargetedUnitNotFoundError,
)
from app.core.localday import local_day_end_utc
from app.models.artifact import LectureArtifact
from app.models.course import Course
from app.models.exam import Exam
from app.models.flashcard import Flashcard
from app.models.flashcard_review import FlashcardReview
from app.models.quiz import QuizQuestion
from app.models.quiz_attempt import QuizAttempt
from app.models.study_plan import StudyPlan
from app.models.summary import Summary
from app.models.targeted_generation import TargetedGeneration
from app.services import exam_service, quota_service, timed_session_service

logger = structlog.get_logger()

# Scoring (Decision 2)
QUIZ_WINDOW_DAYS = 90
QUIZ_HALF_LIFE_DAYS = 14.0
QUIZ_PRIOR_ACCURACY = 0.5
QUIZ_PRIOR_WEIGHT = 2.0
EASE_CEILING = 2.5
EASE_FLOOR = 1.3
CARD_EASE_WEIGHT = 0.5
CARD_LAPSE_WEIGHT = 0.3
CARD_OVERDUE_WEIGHT = 0.2
EVIDENCE_SATURATION = 5.0
MIN_EVIDENCE = 3
CONFIDENCE_FULL_EVIDENCE = 8
WEAK_THRESHOLD = 0.40
SOLID_THRESHOLD = 0.25
EXAM_HALF_LIFE_DAYS = 7.0
EXAM_URGENCY_GAIN = 2.0
SCORE_DECIMALS = 4

# Cold start (Decision 3)
DIAGNOSTIC_QUESTIONS = 3
DIAGNOSTIC_QUESTIONS_MAX = 5
DIAGNOSTIC_URGENCY = 0.5

# "Study tonight" (Decision 4)
DEFAULT_PLAN_MINUTES = 25
MIN_PLAN_MINUTES = 10
MAX_PLAN_MINUTES = 90
MAX_PLAN_ITEMS = 20
FOCUS_WEEKS = 3
REVIEW_SHARE = 0.5
PLAN_ALGORITHM_VERSION = 1

# Targeted generation (Decision 5)
TARGETED_KINDS = ("quiz", "flashcards")
TARGETED_ITEMS_PER_REQUEST = 5
TARGETED_GENERATIONS_PER_DAY = 6
TARGETED_AI_CALLS = 1
DEDUP_JACCARD = 0.8


@dataclass(frozen=True)
class QuizEvidence:
    is_correct: bool
    age_days: float


@dataclass(frozen=True)
class CardEvidence:
    ease_factor: float
    repetition_count: int
    interval_days: int
    overdue_days: float


@dataclass(frozen=True)
class WeekScore:
    status: str
    weakness: float | None
    confidence: float
    urgency: float
    priority: float
    evidence: int


@dataclass(frozen=True)
class WeekWeakSpot:
    course_id: str
    course_code: str
    week: int
    score: WeekScore
    exam_id: str | None
    days_to_exam: int | None


def score_week(
    quiz: list[QuizEvidence], cards: list[CardEvidence], days_to_exam: int | None
) -> WeekScore:
    """Score one (course, week) unit from plain evidence values (ADR 0007 Decision 2).

    Pure and deterministic: the same input gives the same output on every call.

    Args:
        quiz: Answers on the unit's questions, with their age in days.
        cards: SM-2 state of the unit's reviewed, active cards.
        days_to_exam: User-local days to the soonest upcoming exam covering the
            unit, or None.

    Returns:
        The rounded score. A unit with fewer than ``MIN_EVIDENCE`` pieces of
        evidence is ``unknown`` with no weakness and priority 0.
    """
    window = [q for q in quiz if q.age_days <= QUIZ_WINDOW_DAYS]
    evidence = len(window) + len(cards)
    confidence = min(1.0, evidence / CONFIDENCE_FULL_EVIDENCE)
    urgency = 0.0 if days_to_exam is None else 0.5 ** (days_to_exam / EXAM_HALF_LIFE_DAYS)
    if evidence < MIN_EVIDENCE:
        return WeekScore(
            status="unknown",
            weakness=None,
            confidence=round(confidence, SCORE_DECIMALS),
            urgency=round(urgency, SCORE_DECIMALS),
            priority=0.0,
            evidence=evidence,
        )

    weight_q = 0.0
    quiz_weakness = 0.0
    if window:
        weights = [0.5 ** (max(0.0, q.age_days) / QUIZ_HALF_LIFE_DAYS) for q in window]
        weight_q = sum(weights)
        correct = sum(w for w, q in zip(weights, window, strict=True) if q.is_correct)
        accuracy = (correct + QUIZ_PRIOR_WEIGHT * QUIZ_PRIOR_ACCURACY) / (
            weight_q + QUIZ_PRIOR_WEIGHT
        )
        quiz_weakness = 1.0 - accuracy
    wq = min(weight_q, EVIDENCE_SATURATION) / EVIDENCE_SATURATION

    card_weakness = 0.0
    if cards:
        card_weakness = sum(_card_weakness(c) for c in cards) / len(cards)
    wf = min(len(cards), EVIDENCE_SATURATION) / EVIDENCE_SATURATION

    weakness = (wq * quiz_weakness + wf * card_weakness) / (wq + wf)
    rounded = round(weakness, SCORE_DECIMALS)
    if rounded >= WEAK_THRESHOLD:
        status = "weak"
    elif rounded < SOLID_THRESHOLD:
        status = "solid"
    else:
        status = "shaky"
    return WeekScore(
        status=status,
        weakness=rounded,
        confidence=round(confidence, SCORE_DECIMALS),
        urgency=round(urgency, SCORE_DECIMALS),
        priority=round(weakness * (1 + EXAM_URGENCY_GAIN * urgency), SCORE_DECIMALS),
        evidence=evidence,
    )


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _card_weakness(card: CardEvidence) -> float:
    ease = _clamp((EASE_CEILING - card.ease_factor) / (EASE_CEILING - EASE_FLOOR), 0.0, 1.0)
    lapse = 1.0 if card.repetition_count == 0 else 0.0
    overdue = _clamp(card.overdue_days / max(1, card.interval_days), 0.0, 1.0)
    return CARD_EASE_WEIGHT * ease + CARD_LAPSE_WEIGHT * lapse + CARD_OVERDUE_WEIGHT * overdue


# ── Dedup ──────────────────────────────────────────────────────────────

_NON_WORD = re.compile(r"[\W_]+")


def _normalise(text: str) -> str:
    return _NON_WORD.sub(" ", text.casefold()).strip()


def is_duplicate(candidate: str, existing: list[str]) -> bool:
    """True if ``candidate`` repeats one of ``existing`` (ADR 0007 Decision 5).

    Texts are normalised (casefold, non-alphanumerics to spaces, whitespace
    collapsed); they are duplicates when the normalised strings are equal or the
    Jaccard similarity of their word sets is at least ``DEDUP_JACCARD``.
    Deterministic and free of any embedding call.

    Args:
        candidate: The new question stem or card front.
        existing: Stems/fronts to compare against.

    Returns:
        True when a duplicate is found. An empty candidate is never a duplicate.
    """
    norm = _normalise(candidate)
    if not norm:
        return False
    words = set(norm.split())
    for other in existing:
        other_norm = _normalise(other)
        if not other_norm:
            continue
        if other_norm == norm:
            return True
        other_words = set(other_norm.split())
        if len(words & other_words) / len(words | other_words) >= DEDUP_JACCARD:
            return True
    return False


# ── Metrics ────────────────────────────────────────────────────────────

SCORE_SECONDS = Histogram(
    "studyaio_weakspot_score_seconds", "Time to derive the weak-spot scores for one user."
)
PLAN_BUILDS = Counter(
    "studyaio_study_plan_builds_total",
    "Study-tonight plan reads by outcome (built, refreshed, reused).",
    ["outcome"],
)
# `stage` carries the generation kind (quiz | flashcards): the floor-2 label pin allows only
# stage/outcome (see tests/safety/test_floor2_metrics_labels.py), and ADR 0007 names it `kind`.
TARGETED_REQUESTS = Counter(
    "studyaio_targeted_requests_total",
    "Targeted-generation requests by kind (stage) and outcome.",
    ["stage", "outcome"],
)


def _count_plan(outcome: str) -> None:
    PLAN_BUILDS.labels(outcome=outcome).inc()


def _count_request(stage: str, outcome: str) -> None:
    TARGETED_REQUESTS.labels(stage=stage, outcome=outcome).inc()


# ── Ranking, focus and budget (pure) ───────────────────────────────────


@dataclass(frozen=True)
class WeekEvidenceSummary:
    """Human-readable evidence counts behind one unit's score (heatmap tooltip)."""

    quiz_attempts: int
    quiz_accuracy: float | None
    cards_reviewed: int
    avg_ease: float | None
    lapsed_cards: int
    overdue_cards: int


@dataclass(frozen=True)
class WeakSpotDetail:
    """A scored unit with its evidence summary."""

    spot: WeekWeakSpot
    summary: WeekEvidenceSummary


@dataclass(frozen=True)
class PlanCandidate:
    """One study item eligible for tonight's plan, before the budget is applied."""

    item_type: str
    item_id: str
    course_id: str
    course_code: str
    week: int
    reason: str


def _rank_key(detail: WeakSpotDetail) -> tuple:
    spot = detail.spot
    weakness = spot.score.weakness
    days = spot.days_to_exam
    return (
        -spot.score.priority,
        -(weakness if weakness is not None else -1.0),
        days is None,
        days if days is not None else 0,
        spot.course_code,
        spot.week,
    )


def rank_spots(details: list[WeakSpotDetail]) -> list[WeakSpotDetail]:
    """Order units by priority; ties by weakness, exam proximity, course code, week.

    The order is total, so the same evidence always yields the same plan.
    """
    return sorted(details, key=_rank_key)


def clamp_minutes(minutes: int | None) -> int:
    """Clamp a requested budget to the plan range; None means the default."""
    if minutes is None:
        return DEFAULT_PLAN_MINUTES
    return max(MIN_PLAN_MINUTES, min(MAX_PLAN_MINUTES, minutes))


def choose_focus(
    ranked: list[WeakSpotDetail], quiz_units: set[tuple[str, int]]
) -> tuple[list[WeakSpotDetail], WeakSpotDetail | None]:
    """Pick the focus weeks and the optional diagnostic week (Decision 4, steps 1-2).

    Args:
        ranked: Units in ``rank_spots`` order.
        quiz_units: (course_id, week) pairs with at least one active question.

    Returns:
        The top ``FOCUS_WEEKS`` weak/shaky units, and at most one unknown unit to
        diagnose: the most urgent one, included when focus is short or an exam is near.
    """
    focus = [d for d in ranked if d.spot.score.status in ("weak", "shaky")][:FOCUS_WEEKS]
    candidates = [
        (index, d)
        for index, d in enumerate(ranked)
        if d.spot.score.status == "unknown" and (d.spot.course_id, d.spot.week) in quiz_units
    ]
    if not candidates:
        return focus, None
    _, best = min(candidates, key=lambda c: (-c[1].spot.score.urgency, c[0]))
    if len(focus) < FOCUS_WEEKS or best.spot.score.urgency >= DIAGNOSTIC_URGENCY:
        return focus, best
    return focus, None


def _item(candidate: PlanCandidate, minutes: int) -> dict:
    return {
        "item_type": candidate.item_type,
        "item_id": candidate.item_id,
        "course_id": candidate.course_id,
        "course_code": candidate.course_code,
        "week": candidate.week,
        "reason": candidate.reason,
        "minutes": minutes,
    }


def select_plan_items(
    *,
    minutes: int,
    diagnostic: list[PlanCandidate],
    review: list[PlanCandidate],
    practice: list[PlanCandidate],
) -> list[dict]:
    """Apply the time budget (Decision 4, step 3).

    The diagnostic comes first. Of the remaining minutes ``REVIEW_SHARE`` goes to
    review and the rest to practice; minutes one half cannot spend pass to the other.
    Candidate order is preserved, costs are the timed-session ones, and the plan has at
    most ``MAX_PLAN_ITEMS`` items.

    Args:
        minutes: The budget, clamped to the plan range.
        diagnostic: Diagnostic questions, in order.
        review: Due cards, in order.
        practice: Practice questions, in order.

    Returns:
        Item dicts in diagnostic, review, practice order.
    """
    card_cost = timed_session_service.MINUTES_PER_CARD
    quiz_cost = timed_session_service.MINUTES_PER_QUIZ
    diag_out: list[dict] = []
    review_out: list[dict] = []
    practice_out: list[dict] = []

    def count() -> int:
        return len(diag_out) + len(review_out) + len(practice_out)

    def fill(candidates, start, allowance, cost, out) -> tuple[int, int]:
        index = start
        while index < len(candidates) and count() < MAX_PLAN_ITEMS and allowance >= cost:
            out.append(_item(candidates[index], cost))
            allowance -= cost
            index += 1
        return index, allowance

    _, remaining = fill(diagnostic, 0, clamp_minutes(minutes), quiz_cost, diag_out)
    review_budget = int(remaining * REVIEW_SHARE)
    review_at, review_left = fill(review, 0, review_budget, card_cost, review_out)
    practice_at, practice_left = fill(
        practice, 0, remaining - review_budget + review_left, quiz_cost, practice_out
    )
    review_at, practice_left = fill(review, review_at, practice_left, card_cost, review_out)
    fill(practice, practice_at, practice_left, quiz_cost, practice_out)
    return diag_out + review_out + practice_out


# ── Scoring from the database ──────────────────────────────────────────


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _days_between(later: datetime, earlier: datetime) -> float:
    return (_aware(later) - _aware(earlier)).total_seconds() / 86400


@dataclass
class _Inputs:
    courses: dict[str, str]
    units: set[tuple[str, int]]
    quiz_units: set[tuple[str, int]]
    attempts: dict[tuple[str, int], list[tuple[bool, datetime]]]
    reviews: dict[tuple[str, int], list[tuple[float, int, int, datetime]]]
    exams: list[tuple[str, str, datetime, list]]


async def _load_inputs(
    session: AsyncSession, *, user_id: str, course_id: str | None, now: datetime
) -> _Inputs:
    """Fetch the evidence with owner-scoped queries (every one joined to ``courses.user_id``)."""
    course_query = select(Course.id, Course.code).where(
        Course.user_id == user_id, Course.archived_at.is_(None)
    )
    if course_id is not None:
        course_query = course_query.where(Course.id == course_id)
    courses = {cid: code for cid, code in (await session.execute(course_query)).all()}
    inputs = _Inputs(courses, set(), set(), {}, {}, [])
    if not courses:
        return inputs
    owned = Course.user_id == user_id
    ids = list(courses)

    summary_units = select(Summary.course_id, Summary.week).join(
        Course, Course.id == Summary.course_id
    )
    quiz_units = (
        select(QuizQuestion.course_id, QuizQuestion.week)
        .join(Course, Course.id == QuizQuestion.course_id)
        .where(QuizQuestion.archived_at.is_(None))
    )
    card_units = (
        select(Flashcard.course_id, Flashcard.week)
        .join(Course, Course.id == Flashcard.course_id)
        .where(Flashcard.archived_at.is_(None))
    )
    quiz_rows = (await session.execute(quiz_units.where(owned, Course.id.in_(ids)))).all()
    inputs.quiz_units = {(cid, week) for cid, week in quiz_rows}
    inputs.units |= inputs.quiz_units
    for query in (summary_units, card_units):
        rows = (await session.execute(query.where(owned, Course.id.in_(ids)))).all()
        inputs.units |= {(cid, week) for cid, week in rows}

    cutoff = now - timedelta(days=QUIZ_WINDOW_DAYS)
    attempt_rows = (
        await session.execute(
            select(
                QuizQuestion.course_id,
                QuizQuestion.week,
                QuizAttempt.is_correct,
                QuizAttempt.created_at,
            )
            .join(QuizQuestion, QuizQuestion.id == QuizAttempt.quiz_question_id)
            .join(Course, Course.id == QuizQuestion.course_id)
            .where(owned, Course.id.in_(ids), QuizAttempt.created_at >= cutoff)
        )
    ).all()
    for cid, week, correct, created_at in attempt_rows:
        inputs.attempts.setdefault((cid, week), []).append((correct, created_at))

    review_rows = (
        await session.execute(
            select(
                Flashcard.course_id,
                Flashcard.week,
                FlashcardReview.ease_factor,
                FlashcardReview.repetition_count,
                FlashcardReview.interval_days,
                FlashcardReview.next_review_at,
            )
            .join(Flashcard, Flashcard.id == FlashcardReview.flashcard_id)
            .join(Course, Course.id == Flashcard.course_id)
            .where(
                FlashcardReview.user_id == user_id,
                owned,
                Course.id.in_(ids),
                Flashcard.archived_at.is_(None),
            )
        )
    ).all()
    for cid, week, ease, reps, interval, next_at in review_rows:
        inputs.reviews.setdefault((cid, week), []).append((ease, reps, interval, next_at))

    exam_rows = (
        await session.execute(
            select(Exam.id, Exam.course_id, Exam.exam_date, Exam.weeks_scope).where(
                Exam.user_id == user_id, Exam.status == "active", Exam.course_id.in_(ids)
            )
        )
    ).all()
    inputs.exams = [(eid, cid, when, scope or []) for eid, cid, when, scope in exam_rows]
    return inputs


def _next_exam(
    inputs: _Inputs, course_id: str, week: int, *, tz: str | None
) -> tuple[str | None, int | None]:
    """Soonest active exam of the course covering ``week`` whose local date has not passed."""
    today = user_today(tz)
    zone = user_now(tz).tzinfo
    best: tuple[int, datetime, str] | None = None
    for exam_id, exam_course, exam_date, scope in inputs.exams:
        if exam_course != course_id or week not in scope:
            continue
        if _aware(exam_date).astimezone(zone).date() < today:
            continue
        key = (exam_service.days_until(exam_date, tz), _aware(exam_date), exam_id)
        if best is None or key < best:
            best = key
    return (None, None) if best is None else (best[2], best[0])


def _assemble(inputs: _Inputs, *, tz: str | None, now: datetime) -> list[WeakSpotDetail]:
    details: list[WeakSpotDetail] = []
    for cid, week in inputs.units:
        quiz = [
            QuizEvidence(is_correct=correct, age_days=max(0.0, _days_between(now, created_at)))
            for correct, created_at in inputs.attempts.get((cid, week), [])
        ]
        cards = [
            CardEvidence(
                ease_factor=ease,
                repetition_count=reps,
                interval_days=interval,
                overdue_days=max(0.0, _days_between(now, next_at)),
            )
            for ease, reps, interval, next_at in inputs.reviews.get((cid, week), [])
        ]
        exam_id, days = _next_exam(inputs, cid, week, tz=tz)
        score = score_week(quiz, cards, days)
        window = [q for q in quiz if q.age_days <= QUIZ_WINDOW_DAYS]
        summary = WeekEvidenceSummary(
            quiz_attempts=len(window),
            quiz_accuracy=(
                round(sum(q.is_correct for q in window) / len(window), SCORE_DECIMALS)
                if window
                else None
            ),
            cards_reviewed=len(cards),
            avg_ease=(
                round(sum(c.ease_factor for c in cards) / len(cards), SCORE_DECIMALS)
                if cards
                else None
            ),
            lapsed_cards=sum(1 for c in cards if c.repetition_count == 0),
            overdue_cards=sum(1 for c in cards if c.overdue_days > 0),
        )
        spot = WeekWeakSpot(
            course_id=cid,
            course_code=inputs.courses[cid],
            week=week,
            score=score,
            exam_id=exam_id,
            days_to_exam=days,
        )
        details.append(WeakSpotDetail(spot=spot, summary=summary))
    return rank_spots(details)


async def _score_all(
    session: AsyncSession, *, user_id: str, tz: str | None, course_id: str | None
) -> tuple[list[WeakSpotDetail], _Inputs]:
    with SCORE_SECONDS.time():
        now = utc_now()
        inputs = await _load_inputs(session, user_id=user_id, course_id=course_id, now=now)
        details = _assemble(inputs, tz=tz, now=now)
    logger.info(
        "weakspot_scored",
        user_id=user_id,
        units=len(details),
        weak=sum(1 for d in details if d.spot.score.status == "weak"),
    )
    return details, inputs


async def get_weak_spot_details(
    session: AsyncSession, *, user_id: str, tz: str | None, course_id: str | None = None
) -> list[WeakSpotDetail]:
    """Score every (course, week) unit of the caller, with evidence counts, in rank order.

    Args:
        session: Database session.
        user_id: The caller; only their courses and evidence are read.
        tz: The caller's IANA zone (exam proximity is user-local, ADR 0006).
        course_id: Optional single course (must be the caller's, else empty).

    Returns:
        Units ordered by ``rank_spots``; archived courses are excluded.
    """
    details, _ = await _score_all(session, user_id=user_id, tz=tz, course_id=course_id)
    return details


async def get_weak_spots(
    session: AsyncSession, *, user_id: str, tz: str | None, course_id: str | None = None
) -> list[WeekWeakSpot]:
    """Score every (course, week) unit of the caller (ADR 0007 Decision 2).

    Args:
        session: Database session.
        user_id: The caller.
        tz: The caller's IANA zone.
        course_id: Optional single course.

    Returns:
        Units in ranked order.
    """
    details = await get_weak_spot_details(session, user_id=user_id, tz=tz, course_id=course_id)
    return [d.spot for d in details]


# ── Diagnostic ─────────────────────────────────────────────────────────


async def get_diagnostic_questions(
    session: AsyncSession, *, user_id: str, course_id: str, week: int
) -> list[QuizQuestion]:
    """Up to ``DIAGNOSTIC_QUESTIONS_MAX`` existing active questions for a unit (Decision 3).

    Never-attempted first, then fewest attempts, then ``created_at``, then ``id``.

    Args:
        session: Database session.
        user_id: The caller; a course they do not own yields nothing.
        course_id: The course.
        week: The week.

    Returns:
        The questions; fewer than ``DIAGNOSTIC_QUESTIONS`` means the unit needs generation.
    """
    attempts = func.count(QuizAttempt.id)
    result = await session.execute(
        select(QuizQuestion)
        .join(Course, Course.id == QuizQuestion.course_id)
        .outerjoin(QuizAttempt, QuizAttempt.quiz_question_id == QuizQuestion.id)
        .where(
            Course.user_id == user_id,
            QuizQuestion.course_id == course_id,
            QuizQuestion.week == week,
            QuizQuestion.archived_at.is_(None),
        )
        .group_by(QuizQuestion.id)
        .order_by(attempts, QuizQuestion.created_at, QuizQuestion.id)
        .limit(DIAGNOSTIC_QUESTIONS_MAX)
    )
    return list(result.scalars().all())


# ── Study tonight ──────────────────────────────────────────────────────


def _focus_filter(column_course, column_week, pairs: list[tuple[str, int]]):
    return or_(*[and_(column_course == cid, column_week == week) for cid, week in pairs])


async def _review_candidates(
    session: AsyncSession,
    *,
    user_id: str,
    tz: str | None,
    focus: list[WeakSpotDetail],
    courses: dict[str, str],
) -> list[PlanCandidate]:
    """Due cards: focus weeks first (by week priority), then other weeks."""
    cutoff = local_day_end_utc(tz)

    def query(*conditions):
        return (
            select(Flashcard.id, Flashcard.course_id, Flashcard.week)
            .join(Course, Course.id == Flashcard.course_id)
            .outerjoin(
                FlashcardReview,
                and_(
                    FlashcardReview.flashcard_id == Flashcard.id,
                    FlashcardReview.user_id == user_id,
                ),
            )
            .where(
                Course.user_id == user_id,
                Flashcard.archived_at.is_(None),
                or_(FlashcardReview.id.is_(None), FlashcardReview.next_review_at < cutoff),
                *conditions,
            )
            .order_by(FlashcardReview.next_review_at.asc().nulls_last(), Flashcard.id)
            .limit(MAX_PLAN_ITEMS)
        )

    out: list[PlanCandidate] = []
    pairs = [(d.spot.course_id, d.spot.week) for d in focus]
    for cid, week in pairs:
        rows = (
            await session.execute(query(Flashcard.course_id == cid, Flashcard.week == week))
        ).all()
        out += [PlanCandidate("card", fid, c, courses[c], w, "review") for fid, c, w in rows]
    others = [Flashcard.course_id.in_(list(courses))]
    if pairs:
        others.append(~_focus_filter(Flashcard.course_id, Flashcard.week, pairs))
    rows = (await session.execute(query(*others))).all()
    out += [PlanCandidate("card", fid, c, courses[c], w, "review") for fid, c, w in rows]
    return out


async def _practice_candidates(
    session: AsyncSession,
    *,
    user_id: str,
    focus: list[WeakSpotDetail],
    courses: dict[str, str],
) -> list[PlanCandidate]:
    """Focus-week questions: missed (oldest miss first), then never attempted (targeted first)."""
    if not focus:
        return []
    pairs = [(d.spot.course_id, d.spot.week) for d in focus]
    rows = (
        await session.execute(
            select(
                QuizQuestion.id,
                QuizQuestion.course_id,
                QuizQuestion.week,
                QuizQuestion.origin,
                QuizQuestion.created_at,
                QuizAttempt.is_correct,
                QuizAttempt.created_at,
            )
            .join(Course, Course.id == QuizQuestion.course_id)
            .outerjoin(QuizAttempt, QuizAttempt.quiz_question_id == QuizQuestion.id)
            .where(
                Course.user_id == user_id,
                QuizQuestion.archived_at.is_(None),
                _focus_filter(QuizQuestion.course_id, QuizQuestion.week, pairs),
            )
        )
    ).all()
    questions: dict[str, tuple] = {}
    latest: dict[str, tuple[datetime, bool]] = {}
    for qid, cid, week, origin, created_at, correct, attempted_at in rows:
        questions[qid] = (cid, week, origin, created_at)
        if attempted_at is not None and (qid not in latest or attempted_at > latest[qid][0]):
            latest[qid] = (attempted_at, correct)

    def candidate(qid: str, reason: str) -> PlanCandidate:
        cid, week, _, _ = questions[qid]
        return PlanCandidate("quiz", qid, cid, courses[cid], week, reason)

    missed = sorted((q for q, (_, ok) in latest.items() if not ok), key=lambda q: (latest[q][0], q))
    fresh = sorted(
        (q for q in questions if q not in latest),
        key=lambda q: (questions[q][2] != "targeted", questions[q][3], q),
    )
    return [candidate(q, "missed") for q in missed] + [
        candidate(q, "targeted" if questions[q][2] == "targeted" else "new") for q in fresh
    ]


def _focus_json(role: str, detail: WeakSpotDetail) -> dict:
    spot = detail.spot
    return {
        "role": role,
        "course_id": spot.course_id,
        "course_code": spot.course_code,
        "week": spot.week,
        "status": spot.score.status,
        "weakness": spot.score.weakness,
        "priority": spot.score.priority,
        "days_to_exam": spot.days_to_exam,
    }


async def _build_plan(
    session: AsyncSession, *, user_id: str, tz: str | None, minutes: int
) -> tuple[list[dict], list[dict]]:
    """Compute the plan items and the focus record from the current evidence."""
    details, inputs = await _score_all(session, user_id=user_id, tz=tz, course_id=None)
    focus, diag = choose_focus(details, inputs.quiz_units)
    diagnostic: list[PlanCandidate] = []
    if diag is not None:
        questions = await get_diagnostic_questions(
            session, user_id=user_id, course_id=diag.spot.course_id, week=diag.spot.week
        )
        diagnostic = [
            PlanCandidate(
                "quiz",
                q.id,
                diag.spot.course_id,
                diag.spot.course_code,
                diag.spot.week,
                "diagnostic",
            )
            for q in questions[:DIAGNOSTIC_QUESTIONS]
        ]
    review = await _review_candidates(
        session, user_id=user_id, tz=tz, focus=focus, courses=inputs.courses
    )
    practice = await _practice_candidates(
        session, user_id=user_id, focus=focus, courses=inputs.courses
    )
    items = select_plan_items(
        minutes=minutes, diagnostic=diagnostic, review=review, practice=practice
    )
    focus_record = [_focus_json("focus", d) for d in focus]
    if diag is not None:
        focus_record.append(_focus_json("diagnostic", diag))
    return items, focus_record


async def _find_plan(session: AsyncSession, *, user_id: str, plan_date: date) -> StudyPlan | None:
    result = await session.execute(
        select(StudyPlan).where(StudyPlan.user_id == user_id, StudyPlan.plan_date == plan_date)
    )
    return result.scalar_one_or_none()


async def _record_built(session: AsyncSession, plan: StudyPlan, *, user_id: str, outcome: str):
    # The study_plan_built usage event is recorded by the route (the caller's request).
    _count_plan(outcome)
    logger.info(
        "study_plan_built",
        user_id=user_id,
        plan_id=plan.id,
        outcome=outcome,
        items=len(plan.items),
        version=plan.version,
    )


async def get_tonight_plan(
    session: AsyncSession, *, user_id: str, tz: str | None, minutes: int = DEFAULT_PLAN_MINUTES
) -> StudyPlan:
    """Return today's plan, building and storing it on the first read of the local day.

    Later reads that day return the stored plan unchanged (it does not reshuffle while
    the user works); ``minutes`` only matters when the plan is built. The caller commits.

    Args:
        session: Database session.
        user_id: The caller.
        tz: The caller's IANA zone; the plan date is their local date (ADR 0006).
        minutes: Time budget, clamped to the plan range.

    Returns:
        The stored plan row.
    """
    plan, _ = await get_or_build_tonight_plan(session, user_id=user_id, tz=tz, minutes=minutes)
    return plan


async def get_or_build_tonight_plan(
    session: AsyncSession, *, user_id: str, tz: str | None, minutes: int = DEFAULT_PLAN_MINUTES
) -> tuple[StudyPlan, bool]:
    """``get_tonight_plan`` that also says whether this call built the plan.

    Returns:
        ``(plan, built)``; the route records ``study_plan_built`` only when built.
    """
    plan_date = user_today(tz)
    existing = await _find_plan(session, user_id=user_id, plan_date=plan_date)
    if existing is not None:
        _count_plan("reused")
        return existing, False
    budget = clamp_minutes(minutes)
    items, focus = await _build_plan(session, user_id=user_id, tz=tz, minutes=budget)
    plan = StudyPlan(
        user_id=user_id,
        plan_date=plan_date,
        minutes=budget,
        items=items,
        focus=focus,
        algorithm_version=PLAN_ALGORITHM_VERSION,
        version=1,
        built_at=utc_now(),
    )
    try:
        async with session.begin_nested():
            session.add(plan)
            await session.flush()
    except IntegrityError:
        # A concurrent first read of the day won the unique (user_id, plan_date) race.
        winner = await _find_plan(session, user_id=user_id, plan_date=plan_date)
        if winner is None:
            raise
        _count_plan("reused")
        return winner, False
    await _record_built(session, plan, user_id=user_id, outcome="built")
    return plan, True


async def refresh_tonight_plan(
    session: AsyncSession, *, user_id: str, tz: str | None, minutes: int | None = None
) -> StudyPlan:
    """Rebuild today's plan in place and bump its ``version`` (builds it if absent).

    Args:
        session: Database session.
        user_id: The caller.
        tz: The caller's IANA zone.
        minutes: New budget; None keeps the stored one.

    Returns:
        The rewritten plan row. ``built_at`` moves, so ``done`` flags restart.
    """
    plan_date = user_today(tz)
    existing = await _find_plan(session, user_id=user_id, plan_date=plan_date)
    if existing is None:
        return await get_tonight_plan(
            session, user_id=user_id, tz=tz, minutes=clamp_minutes(minutes)
        )
    budget = clamp_minutes(minutes if minutes is not None else existing.minutes)
    items, focus = await _build_plan(session, user_id=user_id, tz=tz, minutes=budget)
    existing.items = items
    existing.focus = focus
    existing.minutes = budget
    existing.algorithm_version = PLAN_ALGORITHM_VERSION
    existing.version = existing.version + 1
    existing.built_at = utc_now()
    await session.flush()
    await _record_built(session, existing, user_id=user_id, outcome="refreshed")
    return existing


async def resolve_plan_items(session: AsyncSession, plan: StudyPlan, *, user_id: str) -> list[dict]:
    """Annotate a stored plan's items for display (Decision 4, "frozen per day").

    Drops items that were archived or whose course is gone since the plan was built, and
    sets ``done``: a card reviewed, or a question attempted, at or after ``built_at``.

    Args:
        session: Database session.
        plan: The caller's stored plan.
        user_id: The caller; every lookup is owner-scoped.

    Returns:
        Item dicts (as stored, with a fresh ``course_code``) plus ``done``.
    """
    stored = list(plan.items or [])
    card_ids = [i["item_id"] for i in stored if i["item_type"] == "card"]
    quiz_ids = [i["item_id"] for i in stored if i["item_type"] == "quiz"]
    alive: dict[tuple[str, str], str] = {}
    done: set[tuple[str, str]] = set()
    if card_ids:
        rows = await session.execute(
            select(Flashcard.id, Course.code)
            .join(Course, Course.id == Flashcard.course_id)
            .where(
                Flashcard.id.in_(card_ids),
                Flashcard.archived_at.is_(None),
                Course.user_id == user_id,
            )
        )
        alive |= {("card", fid): code for fid, code in rows.all()}
        reviewed = await session.execute(
            select(FlashcardReview.flashcard_id).where(
                FlashcardReview.user_id == user_id,
                FlashcardReview.flashcard_id.in_(card_ids),
                FlashcardReview.last_reviewed_at >= plan.built_at,
            )
        )
        done |= {("card", fid) for fid in reviewed.scalars().all()}
    if quiz_ids:
        rows = await session.execute(
            select(QuizQuestion.id, Course.code)
            .join(Course, Course.id == QuizQuestion.course_id)
            .where(
                QuizQuestion.id.in_(quiz_ids),
                QuizQuestion.archived_at.is_(None),
                Course.user_id == user_id,
            )
        )
        alive |= {("quiz", qid): code for qid, code in rows.all()}
        attempted = await session.execute(
            select(QuizAttempt.quiz_question_id)
            .join(QuizQuestion, QuizQuestion.id == QuizAttempt.quiz_question_id)
            .join(Course, Course.id == QuizQuestion.course_id)
            .where(
                Course.user_id == user_id,
                QuizAttempt.quiz_question_id.in_(quiz_ids),
                QuizAttempt.created_at >= plan.built_at,
            )
            .distinct()
        )
        done |= {("quiz", qid) for qid in attempted.scalars().all()}
    return [
        {**item, "course_code": alive[key], "done": key in done}
        for item in stored
        if (key := (item["item_type"], item["item_id"])) in alive
    ]


# ── Targeted generation (request side only; the worker generates) ──────


def utc_day_bounds() -> tuple[datetime, datetime]:
    """The current UTC day as (start, next midnight). Spend caps are UTC (ADR 0006)."""
    now = utc_now()
    start = datetime.combine(now.date(), time.min, tzinfo=UTC)
    return start, start + timedelta(days=1)


async def _has_processed_artifact(
    session: AsyncSession, *, user_id: str, course_id: str, week: int
) -> bool:
    result = await session.execute(
        select(LectureArtifact.id)
        .where(
            LectureArtifact.user_id == user_id,
            LectureArtifact.course_id == course_id,
            LectureArtifact.week == week,
            LectureArtifact.status == "processed",
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _find_in_flight(
    session: AsyncSession, *, user_id: str, course_id: str, week: int, kind: str
) -> TargetedGeneration | None:
    result = await session.execute(
        select(TargetedGeneration)
        .where(
            TargetedGeneration.user_id == user_id,
            TargetedGeneration.course_id == course_id,
            TargetedGeneration.week == week,
            TargetedGeneration.kind == kind,
            TargetedGeneration.status.in_(("queued", "running")),
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _count_generations_today(session: AsyncSession, *, user_id: str, since: datetime) -> int:
    result = await session.execute(
        select(func.count(TargetedGeneration.id)).where(
            TargetedGeneration.user_id == user_id, TargetedGeneration.created_at >= since
        )
    )
    return int(result.scalar() or 0)


async def request_targeted_generation(
    session: AsyncSession, *, user_id: str, user_tier: str, course_id: str, week: int, kind: str
) -> tuple[TargetedGeneration, bool]:
    """Validate and record a targeted-generation request (ADR 0007 Decision 5, steps 2-6).

    Consent (step 1) is the route's dependency. The caller commits, then enqueues the
    worker task; this function never obtains an AI adapter.

    Args:
        session: Database session.
        user_id: The caller.
        user_tier: The caller's tier, for the AI quota.
        course_id: The caller's course.
        week: The week to practise.
        kind: ``quiz`` or ``flashcards``.

    Returns:
        ``(row, created)``: the new ``queued`` row, or the existing in-flight one
        with ``created=False``.

    Raises:
        ValueError: ``kind`` is not a targeted kind.
        TargetedUnitNotFoundError: The caller has no processed artifact for the unit.
        TargetedDailyCapError: The caller used today's allowance (UTC day).
        QuotaExceededError: The tier's daily AI quota would be exceeded.
        GlobalCeilingError: The instance's daily AI ceiling is reached.
    """
    stage = kind
    if kind not in TARGETED_KINDS:
        raise ValueError(f"kind must be one of {TARGETED_KINDS}")
    if not await _has_processed_artifact(session, user_id=user_id, course_id=course_id, week=week):
        _count_request(stage, "not_found")
        raise TargetedUnitNotFoundError()
    scope = {"user_id": user_id, "course_id": course_id, "week": week, "kind": kind}
    existing = await _find_in_flight(session, **scope)
    if existing is not None:
        _count_request(stage, "existing")
        return existing, False
    day_start, reset_at = utc_day_bounds()
    if (
        await _count_generations_today(session, user_id=user_id, since=day_start)
        >= TARGETED_GENERATIONS_PER_DAY
    ):
        _count_request(stage, "capped")
        raise TargetedDailyCapError(limit=TARGETED_GENERATIONS_PER_DAY, reset_at=reset_at)
    try:
        await quota_service.check_ai_quota(session, user_id, user_tier, calls=TARGETED_AI_CALLS)
    except (QuotaExceededError, GlobalCeilingError):
        _count_request(stage, "quota")
        raise
    row = TargetedGeneration(
        user_id=user_id,
        course_id=course_id,
        week=week,
        kind=kind,
        status="queued",
        requested_count=TARGETED_ITEMS_PER_REQUEST,
        topics=[],
    )
    try:
        async with session.begin_nested():
            session.add(row)
            await session.flush()
    except IntegrityError:
        # Two concurrent clicks: the partial unique index let only one in-flight row in.
        winner = await _find_in_flight(session, **scope)
        if winner is None:
            raise
        _count_request(stage, "existing")
        return winner, False
    _count_request(stage, "queued")
    logger.info(
        "targeted_generation_queued",
        user_id=user_id,
        generation_id=row.id,
        course_id=course_id,
        week=week,
        kind=kind,
    )
    return row, True


async def get_targeted_generation(
    session: AsyncSession, generation_id: str, *, user_id: str
) -> TargetedGeneration | None:
    """One of the caller's generations, or None (a foreign id is indistinguishable)."""
    result = await session.execute(
        select(TargetedGeneration).where(
            TargetedGeneration.id == generation_id, TargetedGeneration.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def get_generated_item_ids(
    session: AsyncSession, generation: TargetedGeneration, *, user_id: str
) -> list[str]:
    """Ids of the active items a completed generation created, oldest first."""
    model = QuizQuestion if generation.kind == "quiz" else Flashcard
    result = await session.execute(
        select(model.id)
        .join(Course, Course.id == model.course_id)
        .where(
            Course.user_id == user_id,
            model.targeted_generation_id == generation.id,
            model.archived_at.is_(None),
        )
        .order_by(model.created_at, model.id)
    )
    return list(result.scalars().all())

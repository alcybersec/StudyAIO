"""Pydantic schemas for analytics API."""

from pydantic import BaseModel


class AnalyticsOverviewResponse(BaseModel):
    """Aggregated study statistics overview."""

    total_study_hours: float
    total_cards_reviewed: int
    total_sessions: int
    mastery_pct: float
    total_flashcards: int
    mastered_flashcards: int
    active_courses: int


class HeatmapDay(BaseModel):
    """Single day entry in the study heatmap."""

    date: str
    minutes: float
    cards: int
    sessions: int


class HeatmapResponse(BaseModel):
    """Study heatmap data for a date range."""

    days: list[HeatmapDay]


class RetentionPoint(BaseModel):
    """Single point on the retention curve."""

    interval_bucket: int
    retention_pct: float
    card_count: int


class RetentionResponse(BaseModel):
    """Retention curve data grouped by interval buckets."""

    points: list[RetentionPoint]


class MasteryWeek(BaseModel):
    """Per-week mastery breakdown for a course."""

    course_code: str
    week: int
    total: int
    mastered: int
    learning: int
    new: int
    mastery_pct: float


class MasteryResponse(BaseModel):
    """Mastery breakdown across all weeks."""

    weeks: list[MasteryWeek]


class ExamReadinessResponse(BaseModel):
    """Weighted exam readiness score with component breakdowns."""

    exam_id: str
    title: str
    readiness_score: float
    mastery_score: float
    quiz_score: float
    consistency_score: float
    days_remaining: int
    weak_weeks: list[int]
    flashcard_total: int
    flashcard_mastered: int
    quiz_total: int
    quiz_correct: int
    study_days_last_week: int

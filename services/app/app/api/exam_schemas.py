"""Pydantic schemas for exam endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ExamCreateRequest(BaseModel):
    """Request body for creating an exam."""

    course_code: str
    title: str
    exam_date: datetime
    weeks_scope: list[int] = Field(..., min_length=1)
    target_mastery_pct: int = Field(80, ge=1, le=100)


class ExamUpdateRequest(BaseModel):
    """Request body for updating an exam. All fields optional."""

    title: str | None = None
    exam_date: datetime | None = None
    weeks_scope: list[int] | None = None
    target_mastery_pct: int | None = Field(None, ge=1, le=100)


class ExamResponse(BaseModel):
    """Single exam."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    course_id: str
    title: str
    exam_date: datetime
    weeks_scope: list[int]
    target_mastery_pct: int
    status: str
    created_at: datetime
    updated_at: datetime


class ExamProgressResponse(BaseModel):
    """Exam with comprehensive progress data."""

    exam_id: str
    title: str
    course_id: str
    exam_date: str
    status: str
    days_remaining: int
    mastery_pct: float
    target_mastery_pct: int
    quiz_accuracy: float
    quiz_total: int
    quiz_correct: int
    flashcard_total: int
    flashcard_mastered: int
    weak_weeks: list[int]
    session_count: int
    weeks_scope: list[int]


class WeakTopicResponse(BaseModel):
    """A weak topic analysis result."""

    week: int
    quiz_accuracy: float | None
    quiz_attempts: int
    avg_ease: float | None
    reasons: list[str]
    weakness_score: float


class DailyPlanResponse(BaseModel):
    """A single day's study plan."""

    date: str
    days_until_exam: int
    priority: str
    card_target: int
    quiz_target: int
    focus_weeks: list[int]


class StudySessionRequest(BaseModel):
    """Request body for recording a study session."""

    cards_reviewed: int = Field(0, ge=0)
    quiz_questions_answered: int = Field(0, ge=0)
    quiz_correct: int = Field(0, ge=0)
    duration_seconds: int = Field(0, ge=0)


class StudySessionResponse(BaseModel):
    """Recorded study session."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    exam_id: str | None
    course_id: str
    session_date: str
    cards_reviewed: int
    quiz_questions_answered: int
    quiz_correct: int
    duration_seconds: int


class StudyHistoryDayResponse(BaseModel):
    """Daily study history aggregate."""

    date: str
    cards_reviewed: int
    quiz_answered: int
    quiz_correct: int
    duration_seconds: int
    session_count: int


class ReadinessTopicRow(BaseModel):
    """A single topic (week) row in the readiness drill-down."""

    topic: str
    week: int
    accuracy: float | None = None
    weight: float
    card_count: int


class ReadinessDetailResponse(BaseModel):
    """Topic-level readiness breakdown for an exam."""

    exam_id: str
    title: str
    overall: int
    topics: list[ReadinessTopicRow]

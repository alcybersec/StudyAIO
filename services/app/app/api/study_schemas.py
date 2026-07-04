"""Pydantic schemas for study/SRS endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DueCardResponse(BaseModel):
    """A flashcard due for review, with review state."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    course_id: str
    week: int
    front: str
    back: str
    tags: list | dict
    source_artifact_id: str
    source_page_ref: int
    generation_version: int
    created_at: datetime


class ReviewRequest(BaseModel):
    """Request body for recording a flashcard review."""

    flashcard_id: str
    quality: int = Field(..., ge=0, le=5)


class ReviewResponse(BaseModel):
    """Response after recording a review."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    flashcard_id: str
    ease_factor: float
    interval_days: int
    repetition_count: int
    next_review_at: datetime
    last_reviewed_at: datetime | None


class StudyStatsResponse(BaseModel):
    """Study statistics for a scope."""

    total: int
    due_today: int
    mastered: int
    learning: int
    new: int


class CourseDueCount(BaseModel):
    """Due card count for a single course."""

    course_code: str
    due_count: int


class GlobalStudyStatsResponse(BaseModel):
    """Global study stats for dashboard."""

    total: int
    due_today: int
    mastered: int
    learning: int
    new: int
    per_course: list[CourseDueCount]


class QuizAttemptRequest(BaseModel):
    """Request body for recording a quiz attempt."""

    quiz_question_id: str
    selected_answer: str
    is_correct: bool
    exam_id: str | None = None
    time_spent_ms: int | None = None


class QuizAttemptResponse(BaseModel):
    """Response after recording a quiz attempt."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    quiz_question_id: str
    exam_id: str | None
    selected_answer: str
    is_correct: bool
    time_spent_ms: int | None
    created_at: datetime


class StreakResponse(BaseModel):
    """Study streak data."""

    current_streak: int
    longest_streak: int
    last_study_date: str | None


class TimedPlanRequest(BaseModel):
    """Request body for generating a timed study plan."""

    minutes: int = Field(..., ge=5, le=180, description="Available study time in minutes")
    course_code: str | None = Field(None, description="Optional course code to scope session")
    exam_id: str | None = Field(None, description="Optional exam ID to scope to exam weeks")


class TimedPlanResponse(BaseModel):
    """Response with time-budgeted study plan."""

    total_minutes: int
    card_ids: list[str]
    quiz_ids: list[str]
    estimated_card_minutes: int
    estimated_quiz_minutes: int
    course_code: str | None
    exam_id: str | None


class PlanItem(BaseModel):
    """A single planned study item for a day."""

    course_code: str
    kind: str  # "cards" | "quiz" | "mock"
    target: int
    done: int


class PlanDay(BaseModel):
    """One day of the weekly study plan."""

    day: str
    items: list[PlanItem]


class WeekPlanResponse(BaseModel):
    """The 7-day study plan."""

    days: list[PlanDay]

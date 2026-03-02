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

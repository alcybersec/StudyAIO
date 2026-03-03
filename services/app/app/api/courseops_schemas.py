"""Pydantic schemas for CourseOps API endpoints."""

from datetime import date, datetime

from pydantic import BaseModel, Field


# ── Course Documents ────────────────────────────────────────────

class CourseDocumentResponse(BaseModel):
    """Response schema for a course document."""

    id: str
    course_id: str
    document_type: str
    title: str | None
    original_filename: str
    file_type: str
    sha256: str
    file_size_bytes: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CourseDocumentDetailResponse(CourseDocumentResponse):
    """Detailed response with linked assessments and deadlines."""

    assessments: list["AssessmentResponse"] = []
    deadlines: list["DeadlineResponse"] = []


# ── Assessments ─────────────────────────────────────────────────

class AssessmentResponse(BaseModel):
    """Response schema for an assessment."""

    id: str
    course_id: str
    source_document_id: str | None
    title: str
    assessment_type: str
    weight_pct: float | None
    description: str | None
    weeks_relevant: list[int] | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Deadlines ───────────────────────────────────────────────────

class DeadlineResponse(BaseModel):
    """Response schema for a deadline."""

    id: str
    course_id: str
    assessment_id: str | None
    source_document_id: str | None
    title: str
    due_date: date
    deadline_type: str
    description: str | None
    is_confirmed: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DeadlineUpdateRequest(BaseModel):
    """Request schema for updating a deadline."""

    title: str | None = None
    due_date: date | None = None
    deadline_type: str | None = None
    description: str | None = None
    is_confirmed: bool | None = None


# ── Dashboard ───────────────────────────────────────────────────

class UpcomingDeadlineResponse(BaseModel):
    """Upcoming deadline for dashboard display."""

    id: str
    title: str
    due_date: str
    deadline_type: str
    course_code: str
    is_confirmed: bool


# Rebuild forward refs
CourseDocumentDetailResponse.model_rebuild()

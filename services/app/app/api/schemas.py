"""Pydantic request/response schemas for the API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

# ── Course ────────────────────────────────────────────────────────


class CourseResponse(BaseModel):
    """Single course."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str | None
    term: str | None
    created_at: datetime
    updated_at: datetime


class CourseListItem(CourseResponse):
    """Course with aggregate stats for listing."""

    weeks_covered: int = 0
    total_artifacts: int = 0
    last_updated: datetime | None = None


class WeekSummaryRow(BaseModel):
    """Per-week aggregated data inside a course detail view."""

    week: int
    titles: list[str]
    artifact_count: int
    summary_status: str
    summary_id: str | None
    flashcard_count: int
    quiz_count: int


class CourseDetailResponse(BaseModel):
    """Course with per-week breakdown."""

    course: CourseResponse
    weeks: list[WeekSummaryRow]


# ── Artifact ──────────────────────────────────────────────────────


class ArtifactResponse(BaseModel):
    """Single lecture artifact."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    course_id: str | None
    week: int | None
    title: str | None
    original_filename: str
    file_type: str
    sha256: str
    file_size_bytes: int
    status: str
    created_at: datetime


class UploadResponse(BaseModel):
    """Response after uploading a file."""

    artifact_id: str
    filename: str
    status: str
    pipeline_task_id: str | None = None


# ── Summary ───────────────────────────────────────────────────────


class SummaryResponse(BaseModel):
    """Generated weekly summary."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    course_id: str
    week: int
    content_md: str
    version: int
    source_artifacts: list | None
    created_at: datetime
    updated_at: datetime


# ── Review Items ──────────────────────────────────────────────────


class ReviewItemResponse(BaseModel):
    """A review item requiring human attention."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    review_type: str
    entity_type: str
    entity_id: str
    payload_json: dict
    suggested_values: dict
    status: str
    resolution_json: dict | None
    created_at: datetime
    resolved_at: datetime | None


class ResolveReviewRequest(BaseModel):
    """Request body for resolving a review item."""

    resolution: dict


# ── Pipeline ──────────────────────────────────────────────────────


class PipelineRunResponse(BaseModel):
    """Pipeline run record."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    artifact_id: str
    stage: str
    status: str
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None


class RetryResponse(BaseModel):
    """Response after retrying a failed pipeline."""

    artifact_id: str
    status: str
    retrying_from_stage: str


# ── Dashboard ─────────────────────────────────────────────────────


class ActivityItem(BaseModel):
    """A recent pipeline activity entry."""

    pipeline_run_id: str
    artifact_id: str
    filename: str | None
    stage: str
    status: str
    started_at: str | None
    completed_at: str | None
    duration_ms: int | None


class CourseDueCount(BaseModel):
    """Due card count for a single course."""

    course_code: str
    due_count: int


class DashboardStudyStats(BaseModel):
    """Study stats for the dashboard."""

    total: int
    due_today: int
    mastered: int
    learning: int
    new: int
    per_course: list[CourseDueCount]


class DashboardExamSummary(BaseModel):
    """Exam countdown summary for dashboard."""

    exam_id: str
    title: str
    course_id: str
    course_code: str
    exam_date: str
    days_remaining: int
    mastery_pct: float
    target_mastery_pct: int


class DashboardStreakInfo(BaseModel):
    """Streak info for dashboard."""

    current_streak: int
    longest_streak: int
    last_study_date: str | None


class UpcomingDeadlineItem(BaseModel):
    """Upcoming deadline for dashboard display."""

    id: str
    title: str
    due_date: str
    deadline_type: str
    course_code: str
    is_confirmed: bool


class DashboardResponse(BaseModel):
    """Dashboard aggregate data."""

    pending_review_count: int
    recent_activity: list[ActivityItem]
    courses: list[CourseListItem]
    study_stats: DashboardStudyStats | None = None
    active_exams: list[DashboardExamSummary] = []
    streak: DashboardStreakInfo | None = None
    upcoming_deadlines: list[UpcomingDeadlineItem] = []


# ── Week Detail ───────────────────────────────────────────────────


class WeekDetailResponse(BaseModel):
    """Full detail for a specific course week."""

    course: CourseResponse
    week: int
    summary: SummaryResponse | None
    artifacts: list[ArtifactResponse]


# ── Q&A ──────────────────────────────────────────────────────────


# ── Assets ──────────────────────────────────────────────────────


class FlashcardResponse(BaseModel):
    """A generated flashcard."""

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


class QuizQuestionResponse(BaseModel):
    """A generated quiz question."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    course_id: str
    week: int
    question_type: str
    question: str
    options_json: list | dict | None
    correct_answer: str
    explanation: str
    source_artifact_id: str
    source_page_ref: int
    generation_version: int
    created_at: datetime


# ── Q&A ──────────────────────────────────────────────────────────


# ── Settings ─────────────────────────────────────────────────────


class SettingsResponse(BaseModel):
    """Current application settings."""

    claude_code_path: str
    claude_model: str
    agent_backend: str
    anthropic_api_key: str
    classification_confidence_threshold: float
    flashcard_count_per_week: int
    quiz_question_count_per_week: int
    chunk_size_tokens: int
    chunk_overlap_tokens: int


class SettingsUpdateRequest(BaseModel):
    """Partial update for application settings. All fields optional."""

    claude_code_path: str | None = None
    claude_model: str | None = None
    agent_backend: str | None = None
    anthropic_api_key: str | None = None
    classification_confidence_threshold: float | None = None
    flashcard_count_per_week: int | None = None
    quiz_question_count_per_week: int | None = None
    chunk_size_tokens: int | None = None
    chunk_overlap_tokens: int | None = None


class BatchUploadFileResult(BaseModel):
    """Result for a single file in a batch upload."""

    filename: str
    status: str  # "processing", "duplicate", "error"
    artifact_id: str | None = None
    error: str | None = None


class BatchUploadResponse(BaseModel):
    """Response after batch uploading files."""

    total: int
    succeeded: int
    duplicates: int
    failed: int
    results: list[BatchUploadFileResult]


class QARequest(BaseModel):
    """Request body for asking a question."""

    question: str
    course_code: str | None = None
    week: int | None = None
    top_k: int | None = None


class Citation(BaseModel):
    """A single citation referencing a source chunk."""

    ref: int
    chunk_id: str
    text_snippet: str
    course_code: str
    week: int
    page_ref: int
    artifact_id: str = ""


class QAResponse(BaseModel):
    """Response with AI-generated answer and citations."""

    answer: str
    citations: list[Citation]
    chunks_searched: int

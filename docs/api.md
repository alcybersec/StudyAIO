# StudyAIO API Reference

> Base URL: `http://localhost:8000`
> Interactive docs: `http://localhost:8000/docs` (Swagger UI)

---

## Health

### `GET /health`

Check API server status.

**Response** `200`
```json
{ "status": "ok" }
```

---

## Authentication

All auth endpoints use HttpOnly cookies for session management. Access tokens expire in 15 minutes, refresh tokens in 7 days.

### `GET /api/auth/config`

Public endpoint (no auth required). Returns auth configuration for the frontend.

**Response** `200`
```json
{
  "self_hosted": true,
  "registration_enabled": false,
  "oauth_providers": [],
  "demo_enabled": false
}
```

### `GET /api/auth/demo-login`

Auto-authenticate as the demo user and redirect to dashboard. Rate limited: 10/minute. Requires `demo_enabled=true` in config and a seeded demo user (ID `00000000-0000-0000-0000-000000000002`).

**Response** `302` Redirect to `/` with Set-Cookie (access_token, refresh_token)
**Response** `404` if demo mode is disabled or demo user not found

### `POST /api/auth/register`

Register a new user. Rate limited: 10/minute.

**Body** `RegisterRequest`
**Response** `201` `UserProfileResponse` + Set-Cookie (access_token, refresh_token)

### `POST /api/auth/login`

Authenticate with email and password. Rate limited: 5/minute. If MFA is enabled, `totp_code` is required.

**Body** `LoginRequest`
**Response** `200` `UserProfileResponse` + Set-Cookie | `401` invalid credentials | `403` MFA code required/invalid

### `POST /api/auth/logout`

Clear auth cookies.

**Response** `200` `{ "detail": "Logged out" }`

### `POST /api/auth/refresh`

Rotate access and refresh tokens using the refresh token cookie.

**Response** `200` `{ "detail": "Tokens refreshed" }` + Set-Cookie | `401` invalid/missing refresh token

### `GET /api/auth/me`

Get current user profile. Requires authentication.

**Response** `200` `UserProfileResponse` | `401` not authenticated

### `PUT /api/auth/me`

Update current user profile. Requires authentication.

**Body** `UpdateProfileRequest`
**Response** `200` `UserProfileResponse`

### `POST /api/auth/change-password`

Change password. Requires authentication.

**Body** `ChangePasswordRequest`
**Response** `200` `{ "detail": "Password changed" }` | `401` wrong current password

### `POST /api/auth/forgot-password`

Request password reset. Always returns 202 (no email leak). Rate limited: 5/minute.

**Body** `ForgotPasswordRequest`
**Response** `202`

### `POST /api/auth/reset-password`

Reset password with magic link token.

**Body** `ResetPasswordRequest`
**Response** `200` | `401` invalid/expired/used token

### `POST /api/auth/verify-email`

Verify email with magic link token.

**Body** `VerifyEmailRequest`
**Response** `200`

### `POST /api/auth/mfa/setup`

Generate TOTP secret and QR code. Requires authentication.

**Response** `200` `MFASetupResponse`

### `POST /api/auth/mfa/verify`

Verify TOTP code and enable MFA. Returns backup codes. Requires authentication.

**Body** `MFAVerifyRequest`
**Response** `200` `{ "detail": "MFA enabled", "backup_codes": [...] }`

### `POST /api/auth/mfa/disable`

Disable MFA. Requires authentication.

**Body** `MFADisableRequest`
**Response** `200`

### `GET /api/auth/oauth/{provider}`

OAuth redirect (placeholder — M21).

### `GET /api/auth/oauth/{provider}/callback`

OAuth callback (placeholder — M21).

### `POST /api/auth/magic-link`

Request a magic link. Rate limited: 5/minute. Always returns 202.

**Body** `MagicLinkRequest`
**Response** `202`

### `GET /api/auth/magic/{token}`

Login via magic link (placeholder — M21).

---

## Dashboard

### `GET /api/dashboard`

Aggregated dashboard data: pending review count, recent pipeline activity, and course list with stats.

**Response** `200`
```json
{
  "pending_review_count": 3,
  "recent_activity": [
    {
      "pipeline_run_id": "0192...",
      "artifact_id": "0192...",
      "filename": "Week1_Lecture.pdf",
      "stage": "summarize",
      "status": "completed",
      "started_at": "2026-02-28T10:00:00",
      "completed_at": "2026-02-28T10:01:30",
      "duration_ms": 90000
    }
  ],
  "courses": [
    {
      "id": "0192...",
      "code": "CSIT302",
      "name": "Cybersecurity",
      "term": "2025-S1",
      "created_at": "2026-02-28T09:00:00",
      "updated_at": "2026-02-28T10:00:00",
      "weeks_covered": 8,
      "total_artifacts": 13,
      "last_updated": "2026-02-28T10:00:00"
    }
  ]
}
```

---

## Courses

### `GET /api/courses`

List all courses with aggregate stats.

**Response** `200` — `CourseListItem[]`

Each item includes `weeks_covered`, `total_artifacts`, and `last_updated` in addition to base course fields.

---

### `GET /api/courses/{course_code}`

Get course detail with per-week breakdown.

**Path Parameters**
| Param | Type | Description |
|-------|------|-------------|
| `course_code` | string | Course code (e.g. `CSIT302`) |

**Response** `200`
```json
{
  "course": {
    "id": "0192...",
    "code": "CSIT302",
    "name": "Cybersecurity",
    "term": "2025-S1",
    "created_at": "...",
    "updated_at": "..."
  },
  "weeks": [
    {
      "week": 1,
      "titles": ["Introduction to Security"],
      "artifact_count": 2,
      "summary_status": "completed",
      "summary_id": "0192...",
      "flashcard_count": 0,
      "quiz_count": 0
    }
  ]
}
```

**Errors**
| Status | Detail |
|--------|--------|
| 404 | Course not found |

---

### `GET /api/courses/{course_code}/weeks/{week}`

Full detail for a specific course week: course info, summary (if generated), and artifact list.

**Path Parameters**
| Param | Type | Description |
|-------|------|-------------|
| `course_code` | string | Course code |
| `week` | int | Week number |

**Response** `200`
```json
{
  "course": { "...": "CourseResponse" },
  "week": 1,
  "summary": {
    "id": "0192...",
    "course_id": "0192...",
    "week": 1,
    "content_md": "# CSIT302 — Week 1: Introduction...",
    "version": 1,
    "source_artifacts": ["0192..."],
    "created_at": "...",
    "updated_at": "..."
  },
  "artifacts": [
    {
      "id": "0192...",
      "course_id": "0192...",
      "week": 1,
      "title": "Introduction to Security",
      "original_filename": "Week1.pdf",
      "file_type": "pdf",
      "sha256": "abc123...",
      "file_size_bytes": 1048576,
      "status": "summarized",
      "created_at": "..."
    }
  ]
}
```

**Errors**
| Status | Detail |
|--------|--------|
| 404 | Course not found |

---

## Uploads

### `POST /api/uploads`

Upload a lecture file and start the processing pipeline. Accepts PDF, DOCX, and PPTX files.

**Request** — `multipart/form-data`
| Field | Type | Description |
|-------|------|-------------|
| `file` | binary | Lecture file (.pdf, .docx, .pptx) |

**Response** `201`
```json
{
  "artifact_id": "pending",
  "filename": "Week1_Lecture.pdf",
  "status": "processing",
  "pipeline_task_id": "abc123-..."
}
```

**Errors**
| Status | Detail |
|--------|--------|
| 400 | Missing filename or unsupported file type |
| 409 | Duplicate file (SHA-256 match). Body includes `existing_artifact_id`. |
| 500 | Failed to save file |

---

### `POST /api/uploads/batch`

Batch upload multiple lecture files in a single request. Returns per-file results with succeeded/failed/duplicate counts.

**Request** — `multipart/form-data`
| Field | Type | Description |
|-------|------|-------------|
| `files` | binary[] | Multiple lecture files (.pdf, .docx, .pptx) |

**Response** `201`
```json
{
  "total": 5,
  "succeeded": 3,
  "duplicates": 1,
  "failed": 1,
  "results": [
    { "filename": "Week1.pdf", "status": "processing", "artifact_id": "pending" },
    { "filename": "Week2.pdf", "status": "processing", "artifact_id": "pending" },
    { "filename": "Week3.pdf", "status": "processing", "artifact_id": "pending" },
    { "filename": "Week1.pdf", "status": "duplicate", "artifact_id": "0192..." },
    { "filename": "notes.txt", "status": "error", "error": "Unsupported file type: .txt" }
  ]
}
```

**Errors**
| Status | Detail |
|--------|--------|
| 400 | No files provided |

---

### `GET /api/uploads/{artifact_id}/status`

Get pipeline run history for an uploaded artifact.

**Path Parameters**
| Param | Type | Description |
|-------|------|-------------|
| `artifact_id` | string | Artifact UUID |

**Response** `200` — `PipelineRunResponse[]`
```json
[
  {
    "id": "0192...",
    "artifact_id": "0192...",
    "stage": "ingest",
    "status": "completed",
    "error_message": null,
    "started_at": "2026-02-28T10:00:00",
    "completed_at": "2026-02-28T10:00:05",
    "duration_ms": 5000
  }
]
```

**Errors**
| Status | Detail |
|--------|--------|
| 404 | Artifact not found |

---

### `GET /api/uploads/pipeline-events`

Server-Sent Events (SSE) stream for real-time pipeline progress.

**Query Parameters**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `artifact_id` | string | `""` | Filter events to a specific artifact (empty = all) |

**Event Format**
```
event: pipeline
data: {"artifact_id": "0192...", "stage": "classify", "status": "completed"}
```

---

## Summaries

### `GET /api/summaries/{summary_id}`

Get a generated weekly summary by ID.

**Path Parameters**
| Param | Type | Description |
|-------|------|-------------|
| `summary_id` | string | Summary UUID |

**Response** `200`
```json
{
  "id": "0192...",
  "course_id": "0192...",
  "week": 1,
  "content_md": "# CSIT302 — Week 1: Introduction\n\n## Key Concepts\n...",
  "version": 1,
  "source_artifacts": ["0192..."],
  "created_at": "...",
  "updated_at": "..."
}
```

**Errors**
| Status | Detail |
|--------|--------|
| 404 | Summary not found |

---

## Review Items

### `GET /api/review-items`

List review items, filtered by status.

**Query Parameters**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | string | `"pending"` | Filter: `pending`, `resolved`, `dismissed` |

**Response** `200` — `ReviewItemResponse[]`
```json
[
  {
    "id": "0192...",
    "review_type": "low_confidence_classification",
    "entity_type": "lecture_artifact",
    "entity_id": "0192...",
    "payload_json": { "filename": "lecture.pdf", "raw_text_snippet": "..." },
    "suggested_values": { "course_code": "CSIT302", "week": 1, "confidence": 0.45 },
    "status": "pending",
    "resolution_json": null,
    "created_at": "...",
    "resolved_at": null
  }
]
```

---

### `GET /api/review-items/{review_id}`

Get a single review item by ID.

**Errors**
| Status | Detail |
|--------|--------|
| 404 | Review item not found |

---

### `POST /api/review-items/{review_id}/resolve`

Resolve a review item. Applies the resolution to the referenced entity (e.g., updates artifact classification fields), marks the review as resolved, and resumes the pipeline from the extract stage.

**Request Body**
```json
{
  "resolution": {
    "course_code": "CSIT302",
    "week": 3,
    "title": "Network Security Fundamentals"
  }
}
```

**Response** `200` — Updated `ReviewItemResponse`

**Errors**
| Status | Detail |
|--------|--------|
| 400 | Review item already resolved/dismissed |
| 404 | Review item or referenced entity not found |

---

### `POST /api/review-items/{review_id}/dismiss`

Dismiss a review item without applying changes.

**Response** `200` — Updated `ReviewItemResponse`

**Errors**
| Status | Detail |
|--------|--------|
| 400 | Review item already resolved/dismissed |

---

## Files

### `GET /api/files/{file_type}/{path}`

Serve a file from data directories. Used for rendering images in summaries and downloading artifacts.

**Path Parameters**
| Param | Type | Description |
|-------|------|-------------|
| `file_type` | string | One of: `uploads`, `extractions`, `summaries` |
| `path` | string | Relative path within the type directory |

**Response** `200` — File download (FileResponse)

**Errors**
| Status | Detail |
|--------|--------|
| 400 | Invalid file type |
| 403 | Path traversal detected |
| 404 | File not found |

---

## Error Format

All error responses use a consistent JSON format:

```json
{
  "detail": "Human-readable error message"
}
```

The `409 Conflict` response for duplicate uploads also includes:
```json
{
  "detail": "File already exists as artifact ...",
  "existing_artifact_id": "0192..."
}
```

---

## Study (Spaced Repetition)

### `GET /api/study/due`

Get flashcards due for spaced repetition review. Returns new cards (never reviewed) and overdue cards, sorted with new cards first.

**Query Parameters**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `course_code` | string | — | Filter by course code |
| `week` | integer | — | Filter by week number |
| `limit` | integer | 20 | Max cards to return (1-100) |

**Response** `200` — `DueCardResponse[]`

---

### `POST /api/study/review`

Record a flashcard review with quality rating. Updates SM-2 scheduling state.

**Request Body**
```json
{
  "flashcard_id": "0192...",
  "quality": 3
}
```
Quality: 0 (blackout) to 5 (perfect). Ratings < 3 reset the card.

**Response** `200`
```json
{
  "id": "0192...",
  "flashcard_id": "0192...",
  "ease_factor": 2.5,
  "interval_days": 6,
  "repetition_count": 2,
  "next_review_at": "2026-03-08T10:00:00",
  "last_reviewed_at": "2026-03-02T10:00:00"
}
```

**Errors:** `404` if flashcard not found, `422` if quality out of range.

---

### `GET /api/study/stats`

Get study statistics for a scope.

**Query Parameters**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `course_code` | string | — | Filter by course code |
| `week` | integer | — | Filter by week number |

**Response** `200`
```json
{
  "total": 50,
  "due_today": 12,
  "mastered": 20,
  "learning": 15,
  "new": 15
}
```

---

### `POST /api/study/quiz-attempt`

Record a quiz question attempt. Optionally scoped to an exam.

**Request Body**
```json
{
  "quiz_question_id": "0192...",
  "selected_answer": "B",
  "is_correct": true,
  "exam_id": null,
  "time_spent_ms": 15000
}
```

**Response** `201`
```json
{
  "id": "0192...",
  "quiz_question_id": "0192...",
  "is_correct": true,
  "created_at": "2026-03-03T10:00:00"
}
```

**Errors:** `404` if quiz question not found.

---

### `GET /api/study/streak`

Get global study streak data.

**Query Parameters**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `course_code` | string | — | Filter streak by course |

**Response** `200`
```json
{
  "current_streak": 5,
  "longest_streak": 12,
  "last_study_date": "2026-03-03"
}
```

---

### `POST /api/study/timed-plan`

Generate a time-budgeted study plan with an optimal mix of flashcards and quiz questions for the given time budget.

**Request Body**
```json
{
  "minutes": 30,
  "course_code": "CSIT302",
  "exam_id": null
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `minutes` | integer | Yes | Available study time (5-180) |
| `course_code` | string | No | Scope to a specific course |
| `exam_id` | string | No | Scope to exam week range |

**Response** `200`
```json
{
  "total_minutes": 30,
  "card_ids": ["0192...", "0192..."],
  "quiz_ids": ["0192...", "0192..."],
  "estimated_card_minutes": 18,
  "estimated_quiz_minutes": 12,
  "course_code": "CSIT302",
  "exam_id": null
}
```

Time allocation: ~60% flashcards (~2 min each), ~40% quizzes (~3 min each). Prioritizes due/weak cards first.

---

## Exports

### `GET /api/exports/obsidian/{course_code}`

Export a course as an Obsidian-compatible vault (zip archive with YAML frontmatter, wiki-links, and interconnected markdown files).

**Path Parameters**
| Param | Type | Description |
|-------|------|-------------|
| `course_code` | string | Course code (e.g. `CSIT302`) |

**Query Parameters**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `weeks` | string | `""` | Comma-separated week numbers to include (empty = all) |

**Response** `200` — `application/zip` file download

Vault structure:
```
CourseCode/
├── _Index.md          # Course index with wiki-links to all weeks
├── Week01.md          # Summary with YAML frontmatter
├── Week02.md
├── Flashcards/
│   ├── Week01.md      # Flashcards as callout blocks
│   └── Week02.md
└── Quizzes/
    ├── Week01.md      # Quizzes with collapsible answers
    └── Week02.md
```

**Errors**
| Status | Detail |
|--------|--------|
| 400 | Invalid weeks parameter |
| 404 | Course not found |

---

## Exams

### `POST /api/exams`

Create a new exam with date, week scope, and mastery target.

**Request Body**
```json
{
  "course_code": "CSIT302",
  "title": "Midterm Exam",
  "exam_date": "2026-04-15T09:00:00",
  "weeks_scope": [1, 2, 3, 4, 5],
  "target_mastery_pct": 80
}
```

**Response** `201` — `ExamResponse`

**Errors:** `400` if course not found or exam date is in the past.

---

### `GET /api/exams`

List exams with optional filters.

**Query Parameters**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `course_code` | string | — | Filter by course code |
| `status` | string | — | Filter by status: `active`, `completed`, `archived` |

**Response** `200` — `ExamResponse[]`

---

### `GET /api/exams/{exam_id}`

Get exam detail with comprehensive progress metrics.

**Response** `200` — `ExamProgressResponse`
```json
{
  "exam_id": "0192...",
  "title": "Midterm Exam",
  "course_id": "0192...",
  "exam_date": "2026-04-15T09:00:00",
  "status": "active",
  "days_remaining": 14,
  "mastery_pct": 45.5,
  "target_mastery_pct": 80,
  "quiz_accuracy": 65.0,
  "quiz_total": 20,
  "quiz_correct": 13,
  "flashcard_total": 50,
  "flashcard_mastered": 22,
  "weak_weeks": [2, 4],
  "session_count": 8,
  "weeks_scope": [1, 2, 3, 4, 5]
}
```

**Errors:** `404` if exam not found.

---

### `PUT /api/exams/{exam_id}`

Update exam fields (title, date, scope, target).

**Request Body** — All fields optional.
```json
{
  "title": "Updated Title",
  "exam_date": "2026-04-20T09:00:00",
  "weeks_scope": [1, 2, 3],
  "target_mastery_pct": 90
}
```

**Response** `200` — `ExamResponse`

**Errors:** `404` if exam not found.

---

### `DELETE /api/exams/{exam_id}`

Soft-delete (archive) an exam.

**Response** `204` — No content.

**Errors:** `404` if exam not found.

---

### `GET /api/exams/{exam_id}/schedule`

Get adaptive study schedule for the next N days.

**Query Parameters**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `days` | integer | 7 | Days to plan ahead (1-30) |

**Response** `200` — `DailyPlanResponse[]`
```json
[
  {
    "date": "2026-03-03",
    "days_until_exam": 14,
    "priority": "medium",
    "card_target": 12,
    "quiz_target": 6,
    "focus_weeks": [2, 4]
  }
]
```

Priority scales: `critical` (<=3 days), `high` (<=7), `medium` (<=14), `low` (>14).

**Errors:** `404` if exam not found.

---

### `GET /api/exams/{exam_id}/today`

Get today's adaptive study plan.

**Response** `200` — `DailyPlanResponse`

**Errors:** `404` if exam not found.

---

### `GET /api/exams/{exam_id}/weak-topics`

Identify weak topics by quiz accuracy and flashcard ease.

**Response** `200` — `WeakTopicResponse[]`
```json
[
  {
    "week": 3,
    "quiz_accuracy": null,
    "quiz_attempts": 0,
    "avg_ease": null,
    "reasons": ["unstudied"],
    "weakness_score": 100.0
  }
]
```

Sorted weakest-first. Reasons: `low_quiz_accuracy` (<70%), `low_flashcard_ease` (<2.0), `unstudied`.

**Errors:** `404` if exam not found.

---

### `POST /api/exams/{exam_id}/sessions`

Record a completed study session for an exam.

**Request Body**
```json
{
  "cards_reviewed": 15,
  "quiz_questions_answered": 8,
  "quiz_correct": 6,
  "duration_seconds": 1200
}
```

**Response** `201` — `StudySessionResponse`

**Errors:** `404` if exam not found.

---

### `GET /api/exams/{exam_id}/history`

Get daily study session aggregates.

**Query Parameters**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `days` | integer | 30 | Days of history (1-365) |

**Response** `200` — `StudyHistoryDayResponse[]`
```json
[
  {
    "date": "2026-03-03",
    "cards_reviewed": 25,
    "quiz_answered": 10,
    "quiz_correct": 8,
    "duration_seconds": 1800,
    "session_count": 2
  }
]
```

---

## CourseOps

### `POST /api/courseops/documents`

Upload a course document (outline, rubric, handbook) for AI extraction of assessments and deadlines.

**Request** — `multipart/form-data`
| Field | Type | Description |
|-------|------|-------------|
| `file` | binary | Course document (.pdf, .docx, .pptx) |

**Query Parameters**
| Param | Type | Description |
|-------|------|-------------|
| `course_code` | string | Course code (e.g. `CSIT302`) |
| `document_type` | string | One of: `outline`, `rubric`, `handbook`, `other` |

**Response** `201`
```json
{
  "id": "0192...",
  "course_id": "0192...",
  "document_type": "outline",
  "title": "Outline.pdf",
  "status": "pending",
  "created_at": "2026-03-03T10:00:00"
}
```

**Errors**
| Status | Detail |
|--------|--------|
| 400 | Missing file, unsupported type, or course not found |
| 409 | Duplicate document (SHA-256 match) |

---

### `GET /api/courseops/documents`

List course documents.

**Query Parameters**
| Param | Type | Description |
|-------|------|-------------|
| `course_code` | string | Course code |

**Response** `200` — `CourseDocumentResponse[]`

---

### `GET /api/courseops/documents/{id}`

Get a course document with its extracted assessments and deadlines.

**Response** `200` — `CourseDocumentDetailResponse`

**Errors:** `404` if document not found.

---

### `GET /api/courseops/assessments`

List extracted assessments for a course.

**Query Parameters**
| Param | Type | Description |
|-------|------|-------------|
| `course_code` | string | Course code |

**Response** `200` — `AssessmentResponse[]`

---

### `GET /api/courseops/deadlines`

List extracted deadlines for a course.

**Query Parameters**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `course_code` | string | — | Course code |
| `upcoming` | bool | `false` | Only show future deadlines |

**Response** `200` — `DeadlineResponse[]`

---

### `PUT /api/courseops/deadlines/{id}`

Update or confirm a deadline.

**Request Body** — All fields optional.
```json
{
  "title": "Updated Title",
  "due_date": "2026-04-20",
  "deadline_type": "assignment",
  "description": "Updated description",
  "is_confirmed": true
}
```

**Response** `200` — `DeadlineResponse`

**Errors:** `404` if deadline not found.

---

### `DELETE /api/courseops/deadlines/{id}`

Delete an AI-extracted deadline.

**Response** `204` — No content.

**Errors:** `404` if deadline not found.

---

### `POST /api/courseops/deadlines/{id}/create-exam`

Create an Exam entity from a deadline. Marks the deadline as confirmed.

**Response** `201`
```json
{
  "exam_id": "0192...",
  "title": "Final Exam",
  "exam_date": "2026-06-15T00:00:00",
  "status": "active"
}
```

**Errors:** `404` if deadline not found.

---

### `GET /api/courseops/export/calendar/{course_code}`

Download an .ics calendar file with all deadlines for a course.

**Response** `200` — `text/calendar` file download.

**Errors:** `404` if course not found.

---

### `GET /api/courseops/export/task-plan/{course_code}`

Download a markdown task plan with assessments and deadline checklist.

**Response** `200` — `text/markdown` file download.

**Errors:** `404` if course not found.

---

## Concepts (Knowledge Graph)

### `GET /api/concepts/graph`

Get concept graph with nodes and edges for D3 visualization.

**Query Parameters**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `course_code` | string | — | Filter by course code |

**Response** `200`
```json
{
  "nodes": [
    {
      "id": "0192...",
      "name": "Binary Search",
      "description": "Efficient search algorithm for sorted arrays",
      "category": "algorithm",
      "mention_count": 3,
      "source_weeks": [1, 2],
      "course_id": "0192..."
    }
  ],
  "edges": [
    {
      "id": "0192...",
      "source": "0192...",
      "target": "0192...",
      "relation_type": "uses",
      "confidence": 0.9
    }
  ]
}
```

---

### `GET /api/concepts`

List concepts with optional filters.

**Query Parameters**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `course_code` | string | — | Filter by course code |
| `search` | string | — | Search by concept name |

**Response** `200` — `ConceptNode[]`

---

### `GET /api/concepts/{concept_id}`

Get concept detail with outgoing and incoming relations.

**Response** `200`
```json
{
  "id": "0192...",
  "name": "Binary Search",
  "description": "Efficient search algorithm",
  "category": "algorithm",
  "mention_count": 3,
  "source_artifact_ids": ["0192..."],
  "source_weeks": [1, 2],
  "course_id": "0192...",
  "outgoing_relations": [
    {
      "id": "0192...",
      "concept_id": "0192...",
      "concept_name": "Sorted Array",
      "relation_type": "uses",
      "confidence": 0.9
    }
  ],
  "incoming_relations": [],
  "created_at": "2026-03-05T10:00:00",
  "updated_at": "2026-03-05T12:00:00"
}
```

**Errors:** `404` if concept not found.

---

### `GET /api/concepts/{concept_id}/related`

Find semantically similar concepts via pgvector embedding similarity.

**Response** `200` — `SimilarConceptItem[]`
```json
[
  {
    "id": "0192...",
    "name": "Linear Search",
    "description": "Sequential search",
    "category": "algorithm",
    "course_id": "0192...",
    "similarity": 0.85
  }
]
```

**Errors:** `404` if concept not found.

---

### `POST /api/concepts/extract/{artifact_id}`

Trigger on-demand concept extraction for a specific artifact. Rate limited: 10/minute.

**Response** `200`
```json
{
  "artifact_id": "0192...",
  "concept_count": 5,
  "relation_count": 3
}
```

**Errors:** `404` if artifact not found.

---

## Schema Reference

| Schema | Description |
|--------|-------------|
| `CourseResponse` | id, code, name, term, timestamps |
| `CourseListItem` | CourseResponse + weeks_covered, total_artifacts, last_updated |
| `CourseDetailResponse` | course + weeks[] |
| `WeekSummaryRow` | week, titles[], artifact_count, summary_status/id, flashcard/quiz counts |
| `WeekDetailResponse` | course, week, summary?, artifacts[] |
| `ArtifactResponse` | id, course_id, week, title, filename, file_type, sha256, size, status, created_at |
| `UploadResponse` | artifact_id, filename, status, pipeline_task_id |
| `SummaryResponse` | id, course_id, week, content_md, version, source_artifacts, timestamps |
| `ReviewItemResponse` | id, review_type, entity_type/id, payload, suggested_values, status, resolution, timestamps |
| `PipelineRunResponse` | id, artifact_id, stage, status, error_message, timing |
| `ActivityItem` | pipeline_run_id, artifact_id, filename, stage, status, timing |
| `DashboardResponse` | pending_review_count, recent_activity[], courses[], study_stats?, active_exams[], streak |
| `DashboardStudyStats` | total, due_today, mastered, learning, new, per_course[] |
| `DashboardExamSummary` | id, title, course_code, exam_date, days_remaining, mastery_pct |
| `DashboardStreakInfo` | current_streak, longest_streak, last_study_date |
| `ResolveReviewRequest` | resolution (dict) |
| `DueCardResponse` | flashcard fields (id, front, back, tags, etc.) |
| `ReviewRequest` | flashcard_id, quality (0-5) |
| `ReviewResponse` | id, flashcard_id, ease_factor, interval_days, repetition_count, next_review_at |
| `StudyStatsResponse` | total, due_today, mastered, learning, new |
| `ExamResponse` | id, course_id, title, exam_date, weeks_scope, target_mastery_pct, status, timestamps |
| `ExamProgressResponse` | exam_id, title, course_id, exam_date, status, days_remaining, mastery/quiz/flashcard metrics, weak_weeks, weeks_scope |
| `ExamCreateRequest` | course_code, title, exam_date, weeks_scope, target_mastery_pct |
| `ExamUpdateRequest` | title?, exam_date?, weeks_scope?, target_mastery_pct? |
| `WeakTopicResponse` | week, quiz_accuracy?, quiz_attempts, avg_ease?, reasons[], weakness_score |
| `DailyPlanResponse` | date, days_until_exam, priority, card_target, quiz_target, focus_weeks |
| `StudySessionRequest` | cards_reviewed, quiz_questions_answered, quiz_correct, duration_seconds |
| `StudySessionResponse` | id, exam_id?, course_id, session_date, cards_reviewed, quiz stats, duration |
| `StudyHistoryDayResponse` | date, cards_reviewed, quiz_answered, quiz_correct, duration_seconds, session_count |
| `QuizAttemptRequest` | quiz_question_id, selected_answer, is_correct, exam_id?, time_spent_ms? |
| `QuizAttemptResponse` | id, quiz_question_id, is_correct, created_at |
| `StreakResponse` | current_streak, longest_streak, last_study_date |
| `TimedPlanRequest` | minutes (5-180), course_code?, exam_id? |
| `TimedPlanResponse` | total_minutes, card_ids[], quiz_ids[], estimated_card/quiz_minutes, course_code?, exam_id? |
| `BatchUploadFileResult` | filename, status (processing/duplicate/error), artifact_id?, error? |
| `BatchUploadResponse` | total, succeeded, duplicates, failed, results[] |
| `CourseDocumentResponse` | id, course_id, document_type, title, original_filename, file_type, status, timestamps |
| `CourseDocumentDetailResponse` | CourseDocumentResponse + assessments[], deadlines[] |
| `AssessmentResponse` | id, course_id, source_document_id, title, assessment_type, weight_pct, description, weeks_relevant |
| `DeadlineResponse` | id, course_id, assessment_id, source_document_id, title, due_date, deadline_type, description, is_confirmed |
| `DeadlineUpdateRequest` | title?, due_date?, deadline_type?, description?, is_confirmed? |
| `UpcomingDeadlineItem` | course_code, deadline (DeadlineResponse) |
| `RegisterRequest` | email (EmailStr), username (3-100), password (8-128) |
| `LoginRequest` | email (EmailStr), password, totp_code? |
| `ChangePasswordRequest` | old_password, new_password (8-128) |
| `ForgotPasswordRequest` | email (EmailStr) |
| `ResetPasswordRequest` | token, new_password (8-128) |
| `VerifyEmailRequest` | token |
| `MFASetupResponse` | secret, qr_code_base64, provisioning_uri |
| `MFAVerifyRequest` | totp_code (6 chars), secret |
| `MFADisableRequest` | totp_code (6 chars) |
| `MagicLinkRequest` | email (EmailStr) |
| `UpdateProfileRequest` | username? (3-100), avatar_url? |
| `UserProfileResponse` | id, email, username, role, tier, is_active, email_verified, mfa_enabled, avatar_url, last_login_at, created_at |
| `ConceptNode` | id, name, description, category, mention_count, source_weeks[], course_id |
| `ConceptEdge` | id, source, target, relation_type, confidence |
| `ConceptGraphResponse` | nodes (ConceptNode[]), edges (ConceptEdge[]) |
| `ConceptRelationItem` | id, concept_id, concept_name, relation_type, confidence |
| `ConceptDetailResponse` | ConceptNode + source_artifact_ids[], outgoing_relations[], incoming_relations[], timestamps |
| `SimilarConceptItem` | id, name, description, category, course_id, similarity |
| `ConceptExtractionResponse` | artifact_id, concept_count, relation_count |
| `CalendarConnectRequest` | auth_code |
| `CalendarConnectResponse` | sync_id, calendar_id |
| `CalendarSyncInfo` | id, google_calendar_id, sync_direction, last_synced_at?, event_count |
| `CalendarSyncStatusResponse` | calendars (CalendarSyncInfo[]) |
| `CalendarSyncResult` | pushed, pulled |

---

## Calendar Sync

Google Calendar bidirectional sync. Push deadlines/exams to GCal, pull class schedules.

### `POST /api/calendar/connect`

Exchange OAuth authorization code for tokens and create a CalendarSync. Creates a "StudyAIO" calendar in Google Calendar. Rate limited: 5/minute.

**Request**
```json
{ "auth_code": "4/0AfJohX..." }
```

**Response** `200`
```json
{ "sync_id": "uuid", "calendar_id": "abc@group.calendar.google.com" }
```

### `GET /api/calendar/status`

Return connected calendars with sync status.

**Response** `200`
```json
{
  "calendars": [
    {
      "id": "uuid",
      "google_calendar_id": "abc@group.calendar.google.com",
      "sync_direction": "push",
      "last_synced_at": "2026-03-06T12:00:00",
      "event_count": 12
    }
  ]
}
```

### `POST /api/calendar/sync`

Trigger manual sync for all connected calendars. Rate limited: 5/minute.

**Response** `200`
```json
{ "pushed": 5, "pulled": 2 }
```

### `DELETE /api/calendar/disconnect/{sync_id}`

Disconnect a Google Calendar integration. Revokes token and deletes all event mappings.

**Response** `200`
```json
{ "detail": "Calendar disconnected" }
```

### `POST /api/calendar/webhook`

Google Calendar push notification handler. No auth — verified via channel token headers (`x-goog-channel-id`, `x-goog-resource-id`).

**Response** `200`

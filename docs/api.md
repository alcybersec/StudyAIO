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
| `DashboardResponse` | pending_review_count, recent_activity[], courses[], study_stats? |
| `DashboardStudyStats` | total, due_today, mastered, learning, new, per_course[] |
| `ResolveReviewRequest` | resolution (dict) |
| `DueCardResponse` | flashcard fields (id, front, back, tags, etc.) |
| `ReviewRequest` | flashcard_id, quality (0-5) |
| `ReviewResponse` | id, flashcard_id, ease_factor, interval_days, repetition_count, next_review_at |
| `StudyStatsResponse` | total, due_today, mastered, learning, new |

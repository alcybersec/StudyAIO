# StudyAIO — Progress Tracker

> **Current Milestone:** 2 — Web UI MVP
> **Overall Status:** In Progress

---

## Milestone 1 — Foundation & Pipeline (No UI)

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1.1 | Repo structure, Docker Compose, Makefile | ✅ Done | Git init, GitHub repo (alcybersec/StudyAIO), Docker Compose (api/worker/db/redis), FastAPI app factory, Celery worker, Alembic async setup, structlog, Pydantic Settings. Ports: db=5433, redis=6380 (avoid host conflicts). |
| 1.2 | Database schema + Alembic migrations | ✅ Done | 9 SQLAlchemy models (Course, LectureArtifact, Extraction, Summary, Chunk, Flashcard, QuizQuestion, ReviewItem, PipelineRun). Alembic migration applied. All tables verified with correct columns, indexes, constraints, pgvector column. Fixed uuid7→uuid_extensions import. |
| 1.3 | File extractors (PDF, DOCX, PPTX) | ✅ Done | BaseExtractor ABC + ExtractionResult dataclass. PdfExtractor (pymupdf), DocxExtractor (python-docx), PptxExtractor (python-pptx). Factory function get_extractor(). Per-page/slide text + image extraction. |
| 1.4 | Ingest stage (upload, hash, dedup) | ✅ Done | Celery task ingest_file. SHA-256 dedup via artifact_service. File copied to data/uploads/. Creates LectureArtifact + PipelineRun records. |
| 1.5 | Classify stage (Claude Code CLI + Review Items) | ✅ Done | AgentAdapter ABC with 5 methods. ClaudeCodeAdapter (subprocess). Agent factory. Classify Celery task with confidence scoring. ReviewItem creation for low confidence. Jinja2 prompt template. |
| 1.6 | Extract stage (full extraction with images) | ✅ Done | Celery task extract_artifact. Runs appropriate extractor, saves images to data/extractions/<id>/images/, creates Extraction record with manifest JSON. Idempotent. |
| 1.7 | Summarize stage (markdown + embedded images) | ✅ Done | SummarizationError, summary_service.py (get_week_extractions, merge, create_or_update), summarize.txt + summarize_update.txt prompts, generate_summary() in ClaudeCodeAdapter, summarize_artifact Celery task. Supports multi-artifact weeks and summary updates. |
| 1.8 | Celery pipeline orchestrator | ✅ Done | All tasks accept str\|dict input for chain compatibility (skip on duplicate/waiting_review/failed). orchestrator.py with run_pipeline() (4-stage chain) and resume_pipeline(). `make ingest path=<file>` target. |
| 1.9 | Unit tests + fixtures | ✅ Done | 80 unit tests: extractors (PDF/DOCX/PPTX), services (artifact/summary/review), pipeline stages (ingest/classify/extract/summarize/orchestrator), agent adapter (ClaudeCodeAdapter). pytest.ini, conftest.py with programmatic fixture creators (simple_pdf/docx/pptx). Tests volume-mounted in docker-compose.yml. |
| 1.10 | v0 import script | ✅ Done | scripts/import_v0.py: scans lecture_manager/ directories, creates Course/LectureArtifact/Summary records. SHA-256 dedup, idempotent. `make import-v0` with DATABASE_URL for host execution. |

## Milestone 2 — Web UI MVP

| # | Task | Status | Notes |
|---|------|--------|-------|
| 2.1 | FastAPI endpoints (upload, courses, summaries, review) | ✅ Done | 14 API endpoints: dashboard, courses (list/detail/week), uploads (POST/status/SSE), summaries, review-items (list/get/resolve/dismiss), files. Pydantic schemas, service read functions (course_service, pipeline_service + additions to artifact/review/summary services), SSE pipeline events via Redis pub/sub, exception handlers. 25 new tests (105 total). |
| 2.2 | React project setup (Vite, Tailwind, Router, Query) | ✅ Done | Vite + React 18 + TypeScript. Tailwind CSS v4 with @tailwindcss/vite. React Router (5 routes), React Query, react-markdown. API client layer (typed fetch wrapper + per-resource endpoints). TypeScript types matching API schemas. Query/mutation hooks. SSE hook for pipeline events. Stub pages (Dashboard, Course, WeekView, Upload, ReviewInbox) with AppLayout. UI profile restriction removed from docker-compose.yml. |
| 2.3 | Dashboard page | ✅ Done | ReviewAlert, ActivityFeed (relative time, status badges), CourseCard grid, QuickUpload drop zone. LoadingSpinner + EmptyState for all states. |
| 2.4 | Upload page | ✅ Done | DropZone (drag-and-drop, multi-file, type filtering), FileQueue (status tracking, remove), PipelineProgress (horizontal step indicator driven by SSE). Sequential upload processing. |
| 2.5 | Course page | ✅ Done | PageHeader with breadcrumbs, WeekRow component (week number, titles, artifact count, summary StatusBadge), empty state with upload CTA. |
| 2.6 | Week view | ✅ Done | Tab bar (Summary active, Flashcards/Quiz "Coming Soon"), SummaryTab with react-markdown + remark-gfm + Tailwind prose classes, image path rewriting to /api/files/. ArtifactList (collapsible, file type icons, download links). |
| 2.7 | Review Inbox page | ✅ Done | ReviewCard with SuggestionButtons (confidence %, clickable resolve), CustomResolutionForm (course/week/title inputs), dismiss. Filter tabs (Pending/Resolved/Dismissed). Success/error feedback. |
| 2.8 | Navigation (sidebar + mobile) | ✅ Done | Desktop Sidebar (collapsible, course list with expand/collapse, pending review count badge). MobileNav bottom tab bar. AppLayout with responsive layout. Shared UI components: Badge, StatusBadge, Card, EmptyState, LoadingSpinner, PageHeader (breadcrumbs + actions). @tailwindcss/typography plugin activated. |
| 2.9 | API documentation | ⬜ Not Started | |

## Milestone 3 — Search & Q&A

| # | Task | Status | Notes |
|---|------|--------|-------|
| 3.1 | Indexing stage (chunking, embeddings, pgvector) | ⬜ Not Started | |
| 3.2 | Similarity search with scope filtering | ⬜ Not Started | |
| 3.3 | Q&A endpoint | ⬜ Not Started | |
| 3.4 | Q&A UI with citations | ⬜ Not Started | |
| 3.5 | Jump-to-source from citation | ⬜ Not Started | |

## Milestone 4 — Study Assets

| # | Task | Status | Notes |
|---|------|--------|-------|
| 4.1 | Flashcard generation | ⬜ Not Started | |
| 4.2 | Quiz generation (MCQ + short answer) | ⬜ Not Started | |
| 4.3 | Flashcard UI | ⬜ Not Started | |
| 4.4 | Quiz UI | ⬜ Not Started | |
| 4.5 | Pipeline integration (auto-generate after summarize) | ⬜ Not Started | |

## Milestone 5 — Polish & Portfolio

| # | Task | Status | Notes |
|---|------|--------|-------|
| 5.1 | Error handling pass | ⬜ Not Started | |
| 5.2 | Loading/empty/error states in UI | ⬜ Not Started | |
| 5.3 | Mobile responsiveness pass | ⬜ Not Started | |
| 5.4 | Performance optimization | ⬜ Not Started | |
| 5.5 | Documentation (README, architecture, guides) | ⬜ Not Started | |
| 5.6 | CI pipeline | ⬜ Not Started | |
| 5.7 | Demo recording / portfolio prep | ⬜ Not Started | |

---

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-02-28 | Host ports: db=5433, redis=6380 | Avoid conflicts with existing services on 5432/6379 |
| 2026-02-28 | UI service behind `ui` profile | Not needed for Milestone 1; won't start by default (removed in 2.2) |
| 2026-02-28 | sse-starlette for SSE events | Real-time pipeline progress streaming via Redis pub/sub |
| 2026-02-28 | Tailwind CSS v4 with @tailwindcss/vite | Simpler config, no tailwind.config.js needed |
| 2026-02-28 | uuid7 pip package imports as uuid_extensions | Fixed import in core/utils.py |
| 2026-02-28 | Added alembic/ volume mount to docker-compose.yml | So migrations persist on host, not just in image |

## Issues & Blockers

| Date | Issue | Status | Resolution |
|------|-------|--------|------------|
| | | | |

# StudyAIO — Progress Tracker

> **Current Milestone:** 6 — Quality Hardening (Complete)
> **Overall Status:** Complete (v1 + quality hardening)

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
| 2.9 | API documentation | ✅ Done | docs/api.md with all 14 endpoints. OpenAPI tags + summaries/descriptions on every route for /docs Swagger UI. |

## Milestone 3 — Search & Q&A

| # | Task | Status | Notes |
|---|------|--------|-------|
| 3.1 | Indexing stage (chunking, embeddings, pgvector) | ✅ Done | EmbeddingProvider ABC + SentenceTransformerProvider (all-MiniLM-L6-v2, 384 dims). index_service.py (page-aware chunking, stable IDs, idempotent upsert). index_artifact Celery task. Alembic migration Vector(1536)→Vector(384). Orchestrator updated to 5-stage chain. 25 new tests (130 total). |
| 3.2 | Similarity search with scope filtering | ✅ Done | search_service.py with pgvector cosine distance, JOINs for course/week filtering, similarity scoring. 4 unit tests (134 total). |
| 3.3 | Q&A endpoint | ✅ Done | POST /api/qa/ask endpoint (embed→search→Claude→citations). answer_question() in ClaudeCodeAdapter with Jinja2 prompt. QARequest/QAResponse/Citation schemas. Scope filtering (all/course/week). 5 API tests (139 total). |
| 3.4 | Q&A UI with citations | ✅ Done | QAPage, QuestionForm (scope selector), AnswerDisplay (inline [N] citations), CitationList. React Query mutation hook. /qa route + sidebar/mobile nav items. Session history (local state). |
| 3.5 | Jump-to-source from citation | ✅ Done | ScopedQA component (pre-scoped to course+week). WeekView Q&A tab replaces "Coming Soon". Citations link to /courses/:code/weeks/:week with artifact+page params. Global Q&A citations also navigate to source. |

## Milestone 4 — Study Assets

| # | Task | Status | Notes |
|---|------|--------|-------|
| 4.1 | Backend foundation (exception, prompts, agent, service) | ✅ Done | AssetGenerationError. Jinja2 prompt templates (generate_flashcards.txt, generate_quiz.txt). ClaudeCodeAdapter: generate_flashcards(), generate_quiz(), _parse_json_array_response(). asset_service.py: save/query functions with idempotent versioning. |
| 4.2 | Pipeline stage + orchestrator | ✅ Done | generate_assets Celery task (stage 5, terminal). Two sequential AI calls (flashcards then quiz). Artifact status → "processed". Orchestrator updated to 6-stage chain with "assets" stage entry. |
| 4.3 | API endpoints + schemas | ✅ Done | FlashcardResponse/QuizQuestionResponse schemas. GET /api/assets/flashcards, GET /api/assets/quiz (course_code required, week optional). Router registered in main.py with "assets" tag. |
| 4.4 | Frontend components | ✅ Done | FlashcardsTab (flip cards, keyboard nav, shuffle, badges). QuizTab (MCQ radio+submit, short answer self-assess, progress dots, score summary). Types, endpoints, hooks. WeekViewPage tabs unlocked (no more "Coming Soon"). |
| 4.5 | Tests | ✅ Done | 40 new tests (179 total): asset_service (11), pipeline/assets (8), agents/assets (13), api/assets (8). All tests pass. |

## Milestone 5 — Polish & Portfolio

| # | Task | Status | Notes |
|---|------|--------|-------|
| 5.1 | Pipeline bug fixes + retry endpoint + full stage visibility | ✅ Done | Fixed error_message bug (str(artifact_id) → str(e)) in 5 pipeline stages. Added POST /api/uploads/{id}/retry endpoint. PipelineProgress now shows all 6 stages. 5 new tests. |
| 5.2 | N+1 query elimination | ✅ Done | Added batched list_courses_with_stats() — O(2) queries instead of 4N+1. Dashboard + courses endpoints updated. 2 new tests. |
| 5.3 | UI error recovery + SSE feedback + mobile touch | ✅ Done | ErrorBanner with retry button on Dashboard/Course/Week. ConnectionBanner for SSE status on Upload. Touch targets ≥44px on FlashcardsTab, QuizTab, SuggestionButtons, CustomResolutionForm. |
| 5.4 | GitHub Actions CI | ✅ Done | .github/workflows/ci.yml with backend-tests (pytest) and frontend-checks (tsc + lint) jobs. Dependency caching. |
| 5.5 | README + architecture docs | ✅ Done | README.md with CI badge, Mermaid diagrams, features, tech stack, quick start. docs/architecture.md with system/pipeline/data model diagrams and design decisions. |

## Milestone 6 — Quality Hardening

| # | Task | Status | Notes |
|---|------|--------|-------|
| 6.1 | Integration test infrastructure | ✅ Done | testcontainers-based conftest.py (pgvector/pgvector:pg16 + redis:7-alpine). Session-scoped containers, function-scoped SAVEPOINT rollback. CI-compatible (env var detection skips containers). |
| 6.2 | Integration test suite | ✅ Done | 28 integration tests: DB constraints (5), services (9), API uploads (5), API courses (4), API review items (4), health smoke (1). Real SQL, no mocks. |
| 6.3 | Python linting + coverage + CI | ✅ Done | ruff (E/W/F/I/UP/B/SIM), pyproject.toml. Auto-fixed 61+ violations (import sorting, raise-from, unused vars, zip strict). CI expanded to 4 jobs: python-lint, backend-tests (with --cov), integration-tests (GH Actions services), frontend-checks. Makefile: lint-python, lint-python-fix, coverage. |
| 6.4 | React ErrorBoundary + 404 page | ✅ Done | ErrorBoundary (class component) wraps Outlet in AppLayout. NotFoundPage at catch-all `*` route. Dev-mode error details. 44px touch targets. Fixed FlashcardsTab lint (Math.random impurity). |
| 6.5 | Docker health checks | ✅ Done | API: urllib health check (10s interval, 15s start_period). Worker: celery inspect ping (30s interval, 30s start_period). UI depends_on api: service_healthy. |

## Post-v1 — Fixes & Settings

| # | Task | Status | Notes |
|---|------|--------|-------|
| P.1 | Mount Claude binary into worker container | ✅ Done | Bind mount /home/alex/.local/bin/claude:/usr/local/bin/claude:ro in docker-compose.yml worker service. |
| P.2 | Fix original_filename bug | ✅ Done | Replaced tempfile.NamedTemporaryFile with direct file write using sanitize_filename(). Collision handling with counter. |
| P.3 | Settings page (backend + frontend) | ✅ Done | JSON file at data/settings.json. 7 configurable settings (CLI path, model, threshold, counts, chunk sizes). GET/PUT /api/settings endpoints. SettingsPage with form, validation, success/error feedback. 26 new tests (212 total). Pipeline consumers (claude_code.py, classify.py, assets.py) read from settings service. |

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
| 2026-02-28 | Local embeddings via sentence-transformers (all-MiniLM-L6-v2) | Avoid API keys/costs; EmbeddingProvider ABC is swappable for OpenAI/Voyage later |
| 2026-02-28 | Vector(384) for chunk embeddings | Matches all-MiniLM-L6-v2 output; Alembic migration from Vector(1536) |
| 2026-02-28 | EmbeddingProvider separate from AgentAdapter | Embeddings are deterministic, not generative; different concern from AI agents |

## Issues & Blockers

| Date | Issue | Status | Resolution |
|------|-------|--------|------------|
| | | | |

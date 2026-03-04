# StudyAIO — Progress Tracker

> **Current Milestone:** 28 — AI Study Companion Chat (Complete)
> **Overall Status:** v1 Complete through M15. v2: M16 ✅, M17 ✅, M18 ✅, M20 ✅, M23 ✅, M28 ✅

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

## Milestone 7 — Production Readiness & Quality Gates

| # | Task | Status | Notes |
|---|------|--------|-------|
| 7.1 | UI production Dockerfile (multi-stage build) | ✅ Done | Two-stage Dockerfile: node:20-slim build → nginx:1.27-alpine serve. nginx.conf with SPA fallback, /api proxy (proxy_buffering off for SSE), gzip, immutable cache for hashed assets. .dockerignore. Removed VITE_SSE_URL/VITE_API_URL env vars from docker-compose.yml (nginx handles proxying). CI `npm run build` step added. |
| 7.2 | Production Docker Compose override | ✅ Done | docker-compose.prod.yml: API multi-worker (--workers 2, no --reload), worker concurrency=4, DB/Redis ports unexposed (!override), source bind mounts removed (!override), restart: unless-stopped on all services. Makefile: up-prod, down-prod, build-prod targets. |
| 7.3 | Golden tests for pipeline output structures | ✅ Done | 55 new golden tests in tests/golden/: extraction manifest structure (20 tests across all 3 extractors), summary markdown structure (17 tests for all 8 required sections), study asset structure (18 tests for flashcard/quiz schemas). All tests pass via `make test-golden`. |
| 7.4 | Developer guide | ✅ Done | docs/developer_guide.md with 6 sections: Prerequisites & Setup, Development Workflow, Adding Features, Testing, Architecture Quick Reference, Troubleshooting. README updated with link and production deployment section. |
| 7.5 | Seed fixtures script + Makefile cleanup | ✅ Done | scripts/seed_fixtures.py: creates 2 courses (CSIT302, CSIT314), 7 artifacts, 7 summaries, 35 flashcards, 21 quiz questions, 2 review items. Idempotent. Makefile seed target updated with DATABASE_URL. |

## Milestone 8 — Spaced Repetition (SM-2)

| # | Task | Status | Notes |
|---|------|--------|-------|
| 8.1 | FlashcardReview model + SM-2 service + API endpoints | Done | FlashcardReview model (ease_factor, interval_days, repetition_count, next_review_at). Alembic migration. SM-2 algorithm (calculate_sm2, get_due_cards, record_review, get_study_stats, get_global_study_stats, get_per_course_due_counts). 3 API endpoints: GET /api/study/due, POST /api/study/review, GET /api/study/stats. Dashboard endpoint updated with study_stats. 24 new backend tests. |
| 8.2 | Study Session Page | Done | /study page with 3-phase flow: setup (course/week selector, due count) -> studying (flip card + rate 1-4) -> summary. StudyCard with CSS 3D flip animation. RatingButtons (Again/Hard/Good/Easy with keyboard 1-4). SessionSummary with rating distribution. Keyboard shortcuts (Space=flip, 1-4=rate). |
| 8.3 | Dashboard Study Widget | Done | StudyProgress component showing due count, mastery %, new/learning/mastered breakdown, per-course due counts. "Study Now" CTA. Dashboard response extended with study_stats field. Graceful fallback on error. |
| 8.4 | WeekView FlashcardsTab integration | Done | Study CTA header with due count badge + "Study Now" link (pre-scoped to course+week). Mastered/learning/new stats line. Sidebar + MobileNav updated with Study nav item. |

## Milestone 9 — Exam Mode

| # | Task | Status | Notes |
|---|------|--------|-------|
| 9.1 | Data models + migration | Done | 3 new tables: exams, quiz_attempts, study_sessions. Alembic migration. Models registered. Relationships added to Course and QuizQuestion. |
| 9.2 | Service layer (exam, schedule, streak) | Done | exam_service.py (CRUD, quiz attempts, weak topics, progress), schedule_service.py (adaptive daily plans, priority scaling), streak_service.py (session recording, streak calculation, study history). 32 unit tests. |
| 9.3 | API endpoints + schemas | Done | 12 exam endpoints (CRUD, schedule, today, weak-topics, sessions, history). 2 study endpoint additions (quiz-attempt, streak). Dashboard extended with active_exams + streak. exam_schemas.py + updates to study_schemas.py + schemas.py. 15 API tests. |
| 9.4 | Frontend — Exam pages + dashboard | Done | ExamListPage (cards, create form), ExamDetailPage (progress, schedule, weak topics, history). ExamCreateForm, ExamCountdown, StreakDisplay dashboard widgets. QuizTab records attempts to backend. Types, endpoints, hooks, router, sidebar, mobile nav all updated. |
| 9.5 | Exam-aware study flow + final tests | Done | StudyPage supports ?exam= param (auto-start, session recording on completion). StudySetup shows active exams. SessionSummary shows streak + exam back-link. 23 golden tests for ExamProgress/DailyPlan/WeakTopic structures. Auto-complete past exams on access. 365 total tests. |

## Milestone 10 — Extensibility & Study UX

| # | Task | Status | Notes |
|---|------|--------|-------|
| 10.1 | Direct Anthropic API Adapter | Done | Shared parsing module (agents/parsing.py). AnthropicAPIAdapter implementing all 5 AgentAdapter methods via anthropic SDK. Factory routes by agent_backend setting. Settings page dropdown for backend selection. anthropic_api_key + agent_backend settings. ~34 new tests. |
| 10.2 | Timed Study Sessions | Done | timed_session_service.py (budget N minutes → card/quiz mix, 60/40 split, ~2min/card ~3min/quiz). POST /api/study/timed-plan endpoint. TimedStudyPage with setup→studying→summary flow, CountdownTimer with color warnings, interleaved card/quiz items, keyboard shortcuts. 15 tests. |
| 10.3 | Batch Upload | Done | POST /api/uploads/batch endpoint (multi-file, per-file results, succeeded/failed/duplicates counts). uploadMany() API client helper. UploadPage uses batch for 3+ files. DropZone folder selection via webkitdirectory. 8 tests. |
| 10.4 | Obsidian Export | Done | export_service.py (generates zip vault with YAML frontmatter, wiki-links, callout blocks). GET /api/exports/obsidian/{course_code}. ExportButton component on CoursePage. Vault structure: _Index.md, WeekNN.md, Flashcards/WeekNN.md, Quizzes/WeekNN.md. 38 tests (27 unit + 11 golden). |

## Milestone 11 — CourseOps

| # | Task | Status | Notes |
|---|------|--------|-------|
| 11.0 | Commit existing work | Done | Committed Milestones 8-10 (3 commits, clean git status). |
| 11.1 | Data models + migration | Done | 3 new models (CourseDocument, Assessment, Deadline). Alembic migration d5e6f7g8h9i0. Relationships added to Course. CourseOpsError exception. icalendar dependency. |
| 11.2 | AI extraction + services + Celery task | Done | CourseOpsResult/Assessment/Deadline dataclasses in base.py. extract_course_ops() in ClaudeCode + AnthropicAPI adapters. parse_course_ops_response() in parsing.py. Jinja2 prompt template. courseops_service.py (upload, process, CRUD, dashboard query). calendar_service.py (ICS + task plan MD). Standalone Celery task courseops_task.py. |
| 11.3 | API endpoints | Done | 10 endpoints in courseops router: POST/GET/GET documents, GET assessments, GET/PUT/DELETE deadlines, POST create-exam, GET calendar export, GET task-plan export. Dashboard updated with upcoming_deadlines. |
| 11.4 | Frontend | Done | CourseOpsPage with 4 tabs (Documents, Assessments, Deadlines, Exports). 4 components (DocumentUpload, AssessmentTable, DeadlineTimeline, DeadlineEditModal). Types, endpoints, hooks. Router, CoursePage link, dashboard widget. |
| 11.5 | Tests | Done | 62 new tests: courseops_service (15), calendar_service (5), courseops_extraction (8), api/courseops (15), golden/courseops_structure (19). 506 total tests. |

## Milestone 12 — Hardening & Security

| # | Task | Status | Notes |
|---|------|--------|-------|
| 12.1 | Fix failing test + CI quality gates | ✅ Done | Fixed test_batch_embedding_called_once (mocked chunk_pages to control chunk count). CI: --cov-fail-under=70, golden tests added to pipeline. |
| 12.2 | Upload size limits + security headers + CORS config | ✅ Done | read_upload_with_limit() in core/utils.py (1MB chunked reads, 413 on excess). SecurityHeadersMiddleware (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy). CORS from CORS_ORIGINS env var. anthropic_api_key → SecretStr. nginx.conf security headers. max_upload_size_mb setting. 12 new tests. |
| 12.3 | Multi-stage Dockerfile + non-root user + request ID | ✅ Done | Two-stage Dockerfile (builder with build-essential → runtime with libpq5 only). Non-root studyaio user. Worker runs as root (Claude CLI mount). RequestIDMiddleware (X-Request-ID header, structlog contextvars). 4 new tests. |
| 12.4 | Rate limiting + hardening tests + progress | ✅ Done | slowapi with shared limiter instance. Rate limits on uploads (10/min), batch (5/min), Q&A (20/min), courseops (10/min). Lambda-based limit values (configurable at runtime). Comprehensive hardening test suite (12 tests). 551 total tests. |

## Milestone 13 — Authentication Backend

| # | Task | Status | Notes |
|---|------|--------|-------|
| 13.0 | Commit Milestone 12 work | ✅ Done | Clean baseline before M13. 24 files committed. |
| 13.1 | User model + migration + config + deps | ✅ Done | 3 new models (User, OAuthAccount, MagicLink). Alembic migration e6f7g8h9i0j1. Config: JWT settings, OAuth secrets, self_hosted flag. New deps: PyJWT, argon2-cffi, authlib, pyotp, qrcode, email-validator. |
| 13.2 | Core auth module (hashing + JWT + security) | ✅ Done | core/auth.py (Argon2id hashing, JWT create/decode, magic link tokens). core/security.py (TOTP setup/verify, backup codes, QR code generation). 3 new exception classes (AuthenticationError, AuthorizationError, UserExistsError). 28 tests. |
| 13.3 | User service | ✅ Done | user_service.py: register, authenticate, profile CRUD, password change/reset, email verification, MFA enable/disable, OAuth create/link. Stateless functions, domain exceptions. 25 tests. |
| 13.4 | Auth API endpoints + dependencies | ✅ Done | 17 endpoints in auth router. deps.py (get_current_user, get_optional_user, require_role, require_plan). auth_schemas.py (12 Pydantic models). HttpOnly cookie auth. Exception handlers (401/403/409). Rate limits on login (5/min) and register (10/min). conftest.py: make_user + auth_cookies fixtures. 25 tests. |
| 13.5 | Edge cases + docs | ✅ Done | 11 edge-case tests (MFA login flows, token tampering, password validation, rate limiting, existing endpoints unaffected). Ruff clean. PROGRESS.md + api.md updated. 89 total new tests. 522 passing (+ 8 pre-existing fs-permission failures). |

## Milestone 14 — Authentication Frontend + Protected Routes

| # | Task | Status | Notes |
|---|------|--------|-------|
| 14.0 | Commit Milestone 13 work | ✅ Done | Clean baseline. 27 files committed. |
| 14.1 | Backend — GET /api/auth/config endpoint | ✅ Done | AuthConfigResponse schema. Public endpoint returning self_hosted, registration_enabled, oauth_providers. 3 tests. |
| 14.2 | Frontend — Auth types, API client, token refresh | ✅ Done | 12 auth types in types/index.ts. authApi object with 13 methods in api/auth.ts. 401 auto-refresh with dedup in client.ts (fetchWithRefresh). |
| 14.3 | Frontend — AuthContext + useAuth hook | ✅ Done | AuthProvider (config query, user query, login/register/logout mutations). useAuth() hook + 5 mutation hooks (useChangePassword, useUpdateProfile, useMFASetup, useMFAVerify, useMFADisable). isSelfHosted defaults true. |
| 14.4 | Frontend — Auth pages | ✅ Done | 5 pages (Login, Register, ForgotPassword, ResetPassword, Profile). AuthLayout (centered card). OAuthButtons (provider-aware). MFASetup (QR flow, backup codes, disable). |
| 14.5 | Frontend — Protected routes + router + nav | ✅ Done | ProtectedRoute (self-hosted passthrough, loading spinner, redirect). PublicOnlyRoute (redirect authenticated users). Router restructured (RootLayout→AuthProvider→public/protected). Sidebar user section (avatar, username, sign out). |
| 14.6 | Tests + documentation | ✅ Done | 3 backend tests for auth config. Frontend build passes. PROGRESS.md + api.md updated. 525 total passing tests. |

## Milestone 15 — Multi-Tenant Data Isolation

| # | Task | Status | Notes |
|---|------|--------|-------|
| 15.1 | Schema migration — user_id FKs + UserSettings model | ✅ Done | Added nullable user_id FK to 6 models (Course, LectureArtifact, Exam, StudySession, FlashcardReview, CourseDocument). Created UserSettings model (id, user_id unique FK, settings_json JSONB, theme, dashboard_layout, timestamps). Alembic migration with backfill to default admin + SET NOT NULL. Updated unique constraints: UNIQUE(code, user_id), UNIQUE(sha256, user_id). |
| 15.2 | Service layer user scoping + get_current_user_or_default | ✅ Done | Created get_current_user_or_default dependency (self-hosted returns default admin, SaaS requires JWT). Added user_id parameter to all 14 service modules. Scoped queries with .where(Model.user_id == user_id). Per-user SHA-256 dedup. |
| 15.3 | API routes + pipeline user threading | ✅ Done | Injected user context into all 12 data routers via Depends(get_current_user_or_default). Pipeline carries user_id through all 6 Celery stages via dict payload. resolve_pipeline_input returns (artifact_id, user_id) tuple. SSE events scoped per user. 16 test fixes for new signatures. |
| 15.4 | Settings migration to DB + admin endpoints | ✅ Done | Rewrote settings_service.py from file-based to DB-backed per-user (get_user_settings, update_user_settings, get_effective_setting_async). Sync fallbacks for pipeline. Admin router (GET /api/admin/users, PATCH /api/admin/users/{id}, GET /api/admin/metrics) with require_role("admin"). admin_service.py. |
| 15.5 | Multi-tenant tests + docs | ✅ Done | 64 new tests: user scoping (8), settings DB (8), admin service (8), admin API (8), pipeline threading (10), scoped API (4), deps default user (2), golden structures (6), settings API (5), settings validation (5). 695 total tests (585 unit + 110 golden). PROGRESS.md updated. |

## Milestone 16 — UI Foundation Overhaul (v2)

| # | Task | Status | Notes |
|---|------|--------|-------|
| 16.1 | Frontend deps + CSS theme variables | ✅ Done | Installed motion, @radix-ui (dialog, dropdown-menu, tabs, tooltip, switch), sonner, react-hook-form, zod, @hookform/resolvers. CSS custom properties for 11 theme tokens (light + dark). @custom-variant dark for Tailwind v4. No-flash script in index.html. |
| 16.2 | Shared foundation components | ✅ Done | Skeleton (pulsing placeholder, SkeletonText, SkeletonCard). Toast (Sonner wrapper, mounted in AppLayout). AnimatedCard (motion.div fade-in + slide-up). Sheet (Radix Dialog, bottom/right, AnimatePresence). Barrel exports. Dark mode classes on AppLayout. |
| 16.3 | Sidebar + MobileNav redesign | ✅ Done | Sidebar: grouped sections (Main/Tools), SVG icons replacing unicode, ThemeToggle in footer, theme-aware classes. MobileNav: 5-tab bar (Home, Study, Upload, Q&A, More) with Sheet for overflow items (Review, Settings, Profile). Pending review badge on More button. |
| 16.4 | Page consolidation — StudyHubPage | ✅ Done | Single /study route with 4 Radix Tabs (Flashcards, Timed, Exams, History). Extracted FlashcardsStudyTab, TimedStudyTab, ExamsTab, ExamDetailInline, HistoryTab. URL param sync (?tab=&exam=). Old routes redirect (/timed-study, /exams, /exams/:id). 4 old pages deleted. |
| 16.5 | Form + modal migration | ✅ Done | ExamCreateForm, CustomResolutionForm → react-hook-form + zodResolver. Zod schemas in lib/schemas.ts. DeadlineEditModal, ViewOriginalModal → Radix Dialog. Inline validation errors. Focus trap + escape-to-close. |

## Milestone 17 — Multi-AI Provider System (v2)

| # | Task | Status | Notes |
|---|------|--------|-------|
| 17.1 | OpenAI adapter + backend deps | ✅ Done | Added openai, tiktoken, ollama to requirements.txt. OpenAIAdapter (AsyncOpenAI, all 6 AgentAdapter methods). Config: openai_api_key (SecretStr), openai_model. Settings service updated with new keys + backends. 17 tests. |
| 17.2 | Ollama adapter + factory update | ✅ Done | OllamaAdapter (ollama.AsyncClient, all 6 methods). Factory routes to 4 backends (claude_code, anthropic_api, openai, ollama). Config: ollama_base_url, ollama_model. 16 Ollama tests + 5 factory tests. |
| 17.3 | Embedding providers + parsing resilience | ✅ Done | OpenAIEmbeddingProvider (text-embedding-3-small, 1536d). OllamaEmbeddingProvider (nomic-embed-text, 768d). get_embedding_provider() factory with embedding_backend setting. Resilient parsing: prose preamble stripping, trailing comma removal, single-quote conversion, fallback { to } extraction. 12 embedding tests + 14 enhanced parsing tests. |

## Milestone 18 — Dark Mode & Enhanced Settings (v2)

| # | Task | Status | Notes |
|---|------|--------|-------|
| 18.1 | useTheme hook + ThemeToggle + core UI migration | ✅ Done | useTheme hook (light/dark/system, localStorage, prefers-color-scheme, useSyncExternalStore). ThemeToggle (3-way toggle with SVG icons). Migrated 8 shared UI components (Card, Badge, StatusBadge, EmptyState, LoadingSpinner, PageHeader, ErrorBanner, ConnectionBanner) from hardcoded colors to CSS custom properties. |
| 18.2 | Full dark mode migration (~30 files) | ✅ Done | All dashboard widgets (CourseCard, ReviewAlert, ActivityFeed, QuickUpload, StudyProgress, StreakDisplay, ExamCountdown), upload components (DropZone, FileQueue, PipelineProgress), all pages (DashboardPage, UploadPage, CoursePage, ReviewInboxPage, QAPage, CourseOpsPage, WeekViewPage), auth pages (LoginPage, RegisterPage, ProfilePage, AuthLayout), study components (StudySetup, SessionSummary, StudyCard, RatingButtons, CountdownTimer). |
| 18.3 | Settings page enhancement | ✅ Done | Appearance section (theme selector: light/dark/system buttons). AI Provider section (4 backends: Claude Code, Anthropic API, OpenAI, Ollama with conditional config fields). Embedding backend selector. Classification confidence threshold. Pipeline tuning (flashcard/quiz counts, chunk size/overlap). |

## Milestone 20 — Study Hub Merge (v2)

| # | Task | Status | Notes |
|---|------|--------|-------|
| 20.1 | Completed as part of M16.4 | ✅ Done | StudyHubPage merges StudyPage + TimedStudyPage + ExamListPage + ExamDetailPage into single tabbed view. See M16.4. |

## Milestone 23 — Learning Analytics

| # | Task | Status | Notes |
|---|------|--------|-------|
| 23.1 | AnalyticsSnapshot model + migration | ✅ Done | AnalyticsSnapshot (id, user_id FK, snapshot_date, metrics_json JSONB). UniqueConstraint(user_id, snapshot_date). Alembic migration g8h9i0j1k2l3 (revises f7g8h9i0j1k2). |
| 23.2 | Analytics service (6 functions) | ✅ Done | analytics_service.py: get_overview (study hours, mastery %, cards, sessions), get_study_heatmap (daily totals with gap-fill), get_retention_data (interval buckets, ease-based retention), get_mastery_breakdown (per-week mastered/learning/new via CASE), get_exam_readiness (40% mastery + 30% quiz + 30% consistency), compute_and_store_snapshot (daily upsert). |
| 23.3 | API endpoints + schemas | ✅ Done | 5 GET endpoints: overview, heatmap, retention, mastery, readiness/{exam_id}. Pydantic response models in analytics_schemas.py. Rate-limited (30/min). |
| 23.4 | Frontend — AnalyticsPage + 5 chart components | ✅ Done | AnalyticsPage with Radix Tabs (Overview, Heatmap, Retention, Mastery). OverviewCards (stat cards + exam readiness). StudyHeatmap (GitHub-style SVG grid). RetentionCurve (Recharts LineChart). MasteryBreakdown (Recharts stacked BarChart). ExamReadiness (Recharts RadialBarChart). recharts dependency added. |
| 23.5 | Tests | ✅ Done | 42 new tests: analytics_service (12), api/analytics (8), golden/analytics_structure (22). |

## Milestone 28 — AI Study Companion Chat

| # | Task | Status | Notes |
|---|------|--------|-------|
| 28.1 | ChatSession + ChatMessage models + migration | ✅ Done | ChatSession (user_id FK, course_id nullable FK, title, message_count). ChatMessage (session_id FK CASCADE, role, content, citations_json JSONB, token_count). Alembic migration h9i0j1k2l3m4 (revises g8h9i0j1k2l3). |
| 28.2 | Chat service (5 functions + RAG orchestration) | ✅ Done | chat_service.py: create_session, list_sessions, get_messages, send_message (save user msg → embed + search chunks → build contextual question with history → call agent → save assistant msg), delete_session. Graceful RAG failures, auto-title from first message. |
| 28.3 | API endpoints + schemas | ✅ Done | 5 endpoints: POST/GET /chat/sessions, GET messages, POST message, DELETE session. Rate-limited send_message. chat_schemas.py with SendMessageResponse (user_message + assistant_message). |
| 28.4 | Frontend — ChatPage + 4 components | ✅ Done | ChatPage (session sidebar + message area, mobile Sheet). SessionList (new/delete, relative dates). ChatWindow (auto-scroll, typing indicator). ChatMessage (user/assistant bubbles, react-markdown, citation links). ChatInput (auto-resize textarea, Enter=send, Shift+Enter=newline). |
| 28.5 | Tests | ✅ Done | 43 new tests: chat_service (15), api/chat (11), golden/chat_structure (17). |

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

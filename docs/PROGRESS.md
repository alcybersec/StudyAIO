# StudyAIO — Progress Tracker

> **Current Milestone:** Per-User AI Credentials (Complete)
> **Overall Status:** v1 Complete through M15. v2: M16 ✅, M17 ✅, M18 ✅, M19 ✅, M20 ✅, M21 ✅, M22 ✅, M23 ✅, M24 ✅, M25 ✅, M26 ✅, M27 ✅, M28 ✅, Gap Fill ✅, M29 ✅, M30 ✅, Per-User Credentials ✅

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

## Milestone 22 — PWA + Offline Support

| # | Task | Status | Notes |
|---|------|--------|-------|
| 22.1 | PWA icons + vite-plugin-pwa | ✅ Done | 3 PNG icons (192x192, 512x512, apple-touch-icon 180x180). vite-plugin-pwa with injectManifest strategy. Manifest: name "StudyAIO", theme_color #6366f1, display standalone. |
| 22.2 | Custom service worker | ✅ Done | Workbox: precache static assets, StaleWhileRevalidate for study API (24h, 100 entries), NetworkFirst for general API (1h), CacheFirst for extraction images (7d, 200 entries). Auth endpoints excluded. |
| 22.3 | Offline mutation queue | ✅ Done | IndexedDB queue intercepts POST /api/study/review and /api/study/quiz-attempt on network failure. Returns synthetic 200 responses. Replays on reconnect via SW message. Pending count broadcast to clients. |
| 22.4 | PWA hooks | ✅ Done | useOnlineStatus (useSyncExternalStore + online/offline events), usePendingSync (SW message listener, auto-replay on reconnect). |
| 22.5 | PWA UI components | ✅ Done | OfflineBanner (fixed top, amber offline / primary syncing), InstallPrompt (Chrome beforeinstallprompt + iOS share instructions, localStorage dismiss), PWAUpdateNotify (useRegisterSW, sonner toasts, 60min update check). |
| 22.6 | Layout + nginx integration | ✅ Done | OfflineBanner + PWAUpdateNotify in AppLayout. InstallPrompt on DashboardPage. nginx: sw.js no-cache, manifest.webmanifest correct Content-Type. |

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

## Milestone 25 — Gamification System

| # | Task | Status | Notes |
|---|------|--------|-------|
| 25.1 | Models + Alembic migration | ✅ Done | 6 new models (UserXP, XPEvent, Achievement, UserAchievement, DailyChallenge, UserDailyChallenge). Alembic migration i0j1k2l3m4n5. Relationships on User model. |
| 25.2 | XP, achievement, challenge services | ✅ Done | xp_service.py (level calc, award_xp, summary, leaderboard), achievement_service.py (criteria eval: count/streak/total_xp/level, check/unlock, notified), challenge_service.py (7 templates, deterministic daily, progress tracking). Lazy imports to avoid circular deps. 33 unit tests. |
| 25.3 | API endpoints + schemas | ✅ Done | 6 endpoints on /api/gamification/* (xp, achievements, challenges, leaderboard, unnotified, mark-notified). gamification_schemas.py. Rate-limited 30/min. 15 API tests. |
| 25.4 | Integration hooks + dashboard | ✅ Done | XP awarded on: card review (+5), quiz correct (+10), study session (+20), upload (+15). Challenge progress updated on matching types. Dashboard gamification summary (best-effort). All wrapped in try/except. 7 integration tests. |
| 25.5 | Seed script + golden tests | ✅ Done | scripts/seed_achievements.py (20 achievements, idempotent upsert). Makefile seed-achievements target. 26 golden tests for all gamification structures. |
| 25.6 | Frontend components | ✅ Done | 6 components (XPBar, LevelDisplay, AchievementBadge, AchievementUnlock, DailyChallenges, GamificationWidget). AchievementsPage with tabs (achievements grid + leaderboard). Dashboard widget. React Query hooks with invalidation on study mutations. /achievements route. |

## Milestone 26 — Knowledge Graph & Mind Maps

| # | Task | Status | Notes |
|---|------|--------|-------|
| 26.1 | Data models + Alembic migration | ✅ Done | Concept model (id, user_id FK, course_id FK, name, description, category, embedding Vector(384), source_artifact_ids JSONB, source_weeks JSONB, mention_count). ConceptRelation model (source_concept_id FK, target_concept_id FK, relation_type, confidence). Alembic migration k1l2m3n4o5p6. UniqueConstraints on (user_id, course_id, name) and (source, target, relation_type). |
| 26.2 | AI concept extraction (agent adapter) | ✅ Done | 3 dataclasses (ConceptData, ConceptRelationData, ConceptExtractionResult). Abstract `extract_concepts()` on AgentAdapter. Implemented in all 4 backends. Shared `parse_concept_extraction_response()` in parsing.py with category/relation_type validation, confidence clamping. Jinja2 prompt template. |
| 26.3 | Concept service (business logic) | ✅ Done | concept_service.py: extract_and_save_concepts (AI call + upsert + embeddings), get_concepts (list + filters), get_concept_graph (nodes + edges for D3), get_concept_detail (with relations), find_related_concepts (pgvector cosine similarity). |
| 26.4 | Pipeline integration + on-demand task | ✅ Done | Best-effort concept extraction in assets.py after quiz generation (try/except). Standalone Celery task in concepts_task.py for on-demand re-extraction. |
| 26.5 | API endpoints + schemas | ✅ Done | 5 endpoints: GET graph, GET list, GET detail, GET related, POST extract. concept_schemas.py (7 schemas). Rate-limited extraction (10/min). Course code → course_id resolution helper. |
| 26.6 | Frontend — Knowledge Graph page + D3 | ✅ Done | d3 + @types/d3 deps. ConceptGraph.tsx (D3 force-directed, category colors, zoom/drag, node selection). ConceptDetail.tsx (side panel with relations, similar concepts). ConceptList.tsx (table view). KnowledgeGraphPage.tsx (Radix Tabs graph/list, course filter, search, stats bar, category legend). Router + Sidebar + MobileNav updated. |
| 26.7 | Tests + documentation | ✅ Done | 48 new tests: concept_service (12), api/concepts (7), agents/concept_extraction (11), golden/concept_structure (18). Docs updated. |

## Milestone 19 — Plans & Stripe Integration

| # | Task | Status | Notes |
|---|------|--------|-------|
| 19.1 | Models + migration + config + deps | ✅ Done | Subscription model (user_id FK unique, stripe_customer_id, stripe_subscription_id, plan, status, period dates, cancel_at_period_end). UsageRecord model (user_id FK, record_date, ai_calls/tokens/uploads counts, UNIQUE(user_id, date)). Alembic migration l2m3n4o5p6q7. Config: stripe_api_key/webhook_secret (SecretStr), stripe_pro_price_id, stripe_portal_return_url. stripe>=8.0 pip dep. |
| 19.2 | Billing service + quota service | ✅ Done | billing_service.py: create_checkout_session, create_portal_session, handle_webhook (sub created/updated/deleted), cancel_subscription, record_usage (upsert daily). quota_service.py: check_upload_quota (5/month free), check_ai_quota (20/day free), check_course_quota (1 free). QuotaExceededError exception. Self-hosted/Pro bypass. 47 tests. |
| 19.3 | Billing API endpoints + webhook | ✅ Done | 4 endpoints: POST /billing/checkout, POST /billing/portal, GET /billing/subscription (overview with usage), POST /billing/webhook (Stripe signature verification). billing_schemas.py (7 schemas). Rate-limited checkout/portal (5/min). 402 exception handler for QuotaExceededError. |
| 19.4 | Quota integration + feature gating | ✅ Done | Upload quota check in uploads.py (before save). AI quota check in qa.py, chat.py (send_message), concepts.py (extract). Usage recording (best-effort) after each operation. Self-hosted mode bypasses all checks. 15 quota integration tests. |
| 19.5 | Frontend billing UI + upgrade prompts | ✅ Done | billing.ts API client (3 methods). useBilling hooks (overview, checkout, portal). usePlan hook (plan/isPro/canUpgrade). BillingSection component (usage bars, upgrade/manage buttons). UpgradePrompt modal (shown on 402). ProBadge component. QuotaContext + global 402 handler in API client. SettingsPage billing section. Frontend builds clean. |

## Milestone 21 — Telegram + Email Notifications

| # | Task | Status | Notes |
|---|------|--------|-------|
| 21.1 | Models + migration + config | ✅ Done | NotificationPreference model (user_id FK, channel, event_type, enabled, UniqueConstraint). TelegramLink model (user_id FK unique, chat_id BigInteger, username, verified, link_token unique). Alembic migration m3n4o5p6q7r8. Config: notifications_enabled (default False), telegram_bot_token/webhook_url, smtp_host/port/username/password/from_email/from_name/use_tls. NotificationError + TelegramLinkError exceptions. 3 tests. |
| 21.2 | Email service + templates | ✅ Done | email_service.py: send_email (aiosmtplib, lazy import), send_templated_email, 4 typed senders (pipeline_complete, exam_reminder, cards_due, weekly_digest). 5 Jinja2 templates (base, pipeline_complete, exam_reminder, cards_due, weekly_digest). Best-effort (returns False on failure). aiosmtplib>=2.0 + aiogram>=3.0 deps. 6 tests. |
| 21.3 | Telegram service | ✅ Done | telegram_service.py: generate_link_token (deep-link), verify_link (/start token), unlink, get_link, send_telegram_message (aiogram, lazy import), handle_telegram_webhook, 4 typed senders. Best-effort delivery. 9 tests. |
| 21.4 | Notification dispatch + Celery Beat | ✅ Done | notification_service.py: notify() dispatcher (loads prefs, routes to email/telegram per enabled channels, best-effort), get/update/seed_default preferences, typed notify helpers. notification_tasks.py: send_daily_reminders (8am, due cards), send_weekly_digest (Sunday 9am). Beat schedule in worker.py. Pipeline hook in assets.py (notify_pipeline_complete). Beat service in docker-compose.yml. 8 tests. |
| 21.5 | API endpoints + schemas | ✅ Done | 6 endpoints: GET/PUT /notifications/preferences, POST /notifications/telegram/link, DELETE /notifications/telegram/unlink, POST /notifications/telegram/webhook (no auth, secret header), POST /notifications/test. notification_schemas.py (7 schemas). Rate-limited link generation (5/min) and test (3/min). 8 tests. |
| 21.6 | Frontend UI + golden tests | ✅ Done | notifications.ts API client (5 methods). useNotifications hooks (5 hooks). NotificationsSection component (event×channel toggle grid, test buttons). TelegramLinkCard component (deep-link generation, unlink). 6 notification TypeScript types. SettingsPage includes NotificationsSection. 11 golden tests. Frontend builds clean. |

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

## Milestone 24 — Demo Account + Onboarding Tour

| # | Task | Status | Notes |
|---|------|--------|-------|
| 24.1 | Demo account middleware | ✅ Done | DemoAccountMiddleware (BaseHTTPMiddleware), DemoRestrictionError, demo_enabled config. Blocks writes for demo users (role=demo), allowlists auth paths. 403 JSON with upgrade_url. |
| 24.2 | Demo seed script + auto-login | ✅ Done | scripts/seed_demo.py: creates demo user (ID 00000000...0002, role=demo), 2 courses, 7 artifacts, summaries, ~42 flashcards, ~21 quiz questions, 30 flashcard reviews, 5 study sessions, 1 exam, XP/achievements, chat session, analytics snapshots, review items. GET /api/auth/demo-login endpoint (302 redirect with cookies). Makefile target `seed-demo`. |
| 24.3 | Frontend demo guards + UpgradeCTA | ✅ Done | isDemo in AuthContext, 403 handler in client.ts (setDemoRestrictionHandler), DemoBanner (sticky top bar), UpgradeCTA (Radix Dialog modal), "Demo" badge in Sidebar, UploadPage disabled for demo users. demo_enabled in AuthConfig type. |
| 24.4 | Onboarding tour | ✅ Done | useTour hook (localStorage persistence, 8 steps), OnboardingTour (spotlight overlay via box-shadow, portal), TourTooltip (positioned tooltip with step counter), data-tour attributes on Sidebar nav items. Auto-starts for demo users. "Replay Tour" button on Settings page. |
| 24.5 | Tests + documentation | ✅ Done | 9 middleware tests, 3 login tests, 11 golden tests (22 new tests). 1085 total passing. PROGRESS.md updated. |

## Gap Fill — v2 Feature Gaps

| # | Task | Status | Notes |
|---|------|--------|-------|
| GF.1 | Page transitions (AnimatePresence) | ✅ Done | PageTransition component (motion.div, opacity+y, 150ms ease-in-out). AnimatePresence mode="wait" wrapping Outlet in AppLayout with location.pathname key. |
| GF.2 | Admin Page frontend | ✅ Done | AdminPage with metrics cards (users, artifacts, courses, pipeline runs, storage) + user table (inline role/tier editing, active toggle, pagination, filters). adminApi (listUsers, updateUser, getMetrics), 3 React Query hooks. patch() method added to API client. Admin nav conditional on user.role === 'admin' in Sidebar + MobileNav. /admin route. |
| GF.3 | Dashboard Widget DnD (react-grid-layout) | ✅ Done | react-grid-layout + @types/react-grid-layout installed. WidgetRegistry (8 widgets, lg/sm layouts), useDashboardLayout hook (reads/persists layout via settings API, debounced 500ms save), DashboardCustomizer (Radix Dialog, widget show/hide toggles + reset). DashboardPage rewritten with ResponsiveGridLayout. Mobile: single column, no drag. dashboard_layout added to Settings type. |
| GF.4 | Web Push Notifications | ✅ Done | PushSubscription model + Alembic migration n4o5p6q7r8s9. push_service.py (subscribe/unsubscribe/send, stale subscription cleanup on 410). VAPID config (public_key, private_key, admin_email). "push" channel added to notification_service dispatch. 3 API endpoints (vapid-key, subscribe, unsubscribe). Service worker push+notificationclick handlers. usePushNotifications hook + PushNotificationToggle component. pywebpush + py-vapid deps. generate_vapid_keys.py script. 14 unit tests + 21 golden tests. |
| GF.5 | Chat Streaming (SSE) | ✅ Done | stream_answer() async generator on AgentAdapter base (default: yield full answer). Native streaming on AnthropicAPIAdapter (client.messages.stream text_stream) + OpenAIAdapter (create stream=True). stream_message() in chat_service (yields user_message→tokens→done events, saves to DB). POST /chat/sessions/{id}/messages/stream SSE endpoint via sse-starlette. Frontend: useStreamingChat hook (ReadableStream SSE parsing, token accumulation, cache invalidation), StreamingMessage component (blinking cursor), ChatWindow rewritten for streaming. chatApi.streamMessage (standalone fetch for POST SSE). 13 unit tests + 23 golden tests (existing admin golden). |

**Tests:** 71 new tests (27 unit + 44 golden). ~1156 total.

## Milestone 27 — Google Calendar Bidirectional Sync

| # | Task | Status | Notes |
|---|------|--------|-------|
| 27.1 | Models + Migration + Config + Dependencies | ✅ Done | CalendarSync + CalendarEvent models. Alembic migration o5p6q7r8s9t0. google_calendar_scopes config. CalendarSyncError exception. google-api-python-client + google-auth-oauthlib + google-auth-httplib2 deps. |
| 27.2 | Google Calendar Service | ✅ Done | gcal_service.py: connect_google_calendar (OAuth code exchange, creates StudyAIO calendar), disconnect_calendar (revoke + delete), get_sync_status, push_events (deadlines + exams → GCal, hash-based change detection), pull_events (incremental sync via syncToken), sync_calendar (orchestrate push/pull by direction), handle_gcal_webhook. Lazy imports for Google libs. |
| 27.3 | API Endpoints + Celery Beat Task | ✅ Done | 5 endpoints: POST /calendar/connect, POST /calendar/sync, GET /calendar/status, DELETE /calendar/disconnect/{sync_id}, POST /calendar/webhook. Rate limited 5/min on connect+sync. calendar_task.py Celery task (sync_all_calendars every 15min via beat). Router registered in main.py. |
| 27.4 | Frontend UI | ✅ Done | CalendarSyncSection component (connect via Google OAuth popup, sync now, disconnect with confirmation). Integrated in SettingsPage. calendar.ts API client, useCalendar.ts hooks (4 hooks). "Sync Calendar" button on ExamsTab + calendar icon on DeadlineTimeline (shown when calendar connected). TypeScript types added. |
| 27.5 | Tests + Documentation | ✅ Done | 10 service tests (hash, connect, disconnect, status, push create/skip/update, pull import/incremental, bidirectional sync). 5 API tests (connect, status, disconnect, sync, webhook). 5 golden tests (status, connect response, event mapping, sync result, webhook). PROGRESS.md + api.md updated. |

**Tests:** ~20 new tests (15 unit + 5 golden). ~1176 total.

## Milestone 29 — Cloud Infrastructure + Self-Hosted Packaging

| # | Task | Status | Notes |
|---|------|--------|-------|
| 29.1 | Storage Backend Abstraction Layer | ✅ Done | StorageBackend ABC with `put`, `put_file`, `get`, `get_to_file`, `exists`, `delete`, `get_url`, `ensure_dir` + sync wrappers. LocalStorageBackend (pathlib under data_dir). S3StorageBackend (lazy boto3 client, prefix support, CDN/presigned URLs). `get_storage()` singleton + `reset_storage()`. `normalize_storage_key()` helper. Config: storage_backend, s3_bucket, s3_region, s3_access_key_id (SecretStr), s3_secret_access_key (SecretStr), s3_endpoint_url, s3_prefix, cdn_base_url. `compute_sha256_from_bytes()` utility. boto3 dep added. 20 unit tests. |
| 29.2 | Migrate All File I/O to Storage Backend | ✅ Done | 10 files migrated: uploads.py (put), files.py (serve via storage, local FileResponse / S3 Response), courseops.py (put/delete), artifact_service.py (put_file, relative keys), extract.py (local resolve_path / S3 download-extract-upload), classify.py (storage-backed text preview), summarize.py (put), summary_service.py (build_summary_storage_key), courseops_task.py (storage resolution). DB stores relative storage keys. All 927 existing tests pass. |
| 29.3 | Self-Hosted Compose + Setup Script | ✅ Done | docker-compose.selfhosted.yml: Traefik v3.2 reverse proxy, Let's Encrypt ACME, restart: unless-stopped, port restrictions (no host db/redis), backup sidecar (postgres:16-alpine). scripts/setup-selfhosted.sh: interactive prereq checks, domain/email/password prompts, auto JWT secret, .env generation, build+start+migrate. scripts/backup.sh: pg_dump+gzip, data tar, retention policy (default 7), optional S3 upload. Makefile targets: up-selfhosted, down-selfhosted, backup. |
| 29.4 | Cloud Infrastructure + CI/CD | ✅ Done | AWS Terraform (infra/cloud/aws/): VPC (2 AZ, public/private subnets, NAT gateway), RDS PostgreSQL 16 (encrypted, 7-day backups), ElastiCache Redis 7.1, S3 (versioned, encrypted, private), ECS Fargate (API + worker services), ALB (HTTP→HTTPS redirect), IAM (least-privilege S3 access), CloudWatch (30-day retention). docker-compose.cloud.yml (single-VM with external RDS/Redis/S3). .github/workflows/deploy.yml (build→GHCR→ECS deploy on main/tag). OCI image labels on both Dockerfiles. |
| 29.5 | Prometheus Metrics + Deployment Docs | ✅ Done | Conditional Prometheus instrumentation in main.py (prometheus-fastapi-instrumentator, /metrics endpoint when PROMETHEUS_ENABLED=true). prometheus_enabled config field. docs/deployment.md: self-hosted quickstart, manual setup, AWS Terraform, single-VM cloud, CI/CD pipeline, storage config, backup/restore, monitoring, env var reference, troubleshooting. 2 metrics tests. |

**Tests:** ~22 new tests (20 storage + 2 metrics). All 927 unit + 232 golden tests pass.

## Milestone 30 — Final Polish, E2E Tests, Launch Prep

| # | Task | Status | Notes |
|---|------|--------|-------|
| 30.1 | Frontend Performance Optimization | ✅ Done | Route-level code splitting: all 20 page imports converted to React.lazy() with named-export adapter. Vite manualChunks: vendor-react, vendor-query, vendor-ui (radix+motion+sonner), vendor-viz (d3+recharts), vendor-pdf, vendor-forms (react-hook-form+zod). Suspense boundary in AppLayout wrapping Outlet inside AnimatePresence. OG meta tags in index.html. Fixed pre-existing react-grid-layout v2 API breakage (WidthProvider → useContainerWidth, Layout → LayoutItem, Layouts → ResponsiveLayouts). Build produces 15+ chunks. |
| 30.2 | Accessibility + Error Handling Pass | ✅ Done | Skip-to-content link (#main-content) in AppLayout. aria-current="page" on all active nav links (Sidebar NavSection, courses, admin, settings; MobileNav tabs + More sheet items). aria-label on collapse button (Sidebar), More button (MobileNav), chat sessions toggle (ChatPage). ErrorBoundary theme-aware (text-text, bg-surface-alt, dark:bg-red-950). ErrorBanner added to ChatPage (sessions error), KnowledgeGraphPage (graph/list errors), AdminPage (metrics/users errors). |
| 30.3 | Playwright E2E Test Suite | ✅ Done | @playwright/test installed. playwright.config.ts (chromium, baseURL localhost:3001, screenshot on failure). 30 tests across 8 spec files: auth (5), dashboard (3), upload (4), course (4), study (4), chat (3), search-qa (3), navigation (4). Tests adapt to self-hosted vs SaaS mode. Shared fixtures in e2e/fixtures.ts (testEmail, registerUser, loginViaAPI, seedCourse, buildMinimalPDF). |
| 30.4 | Documentation Update | ✅ Done | api.md: added 40 missing endpoint docs (notifications 9, gamification 6, chat 6, analytics 5, billing 4, admin 3, settings 2, assets 2). Now covers all 111 endpoints. architecture.md: v2 system diagram (multi-AI, storage, external services), 38-model ER diagram, auth flow, storage backends, deployment topologies, code splitting. README.md: updated stats, v2 feature list, project structure, deployment commands. migration-v1-v2.md: new file with DB changes, env vars, breaking API changes, storage migration, rollback steps. PROGRESS.md: M30 table added. |

**Tests:** 30 new E2E tests (Playwright). Total: ~579 backend + 30 E2E = ~609 tests.

## Technical Hardening

| # | Task | Status | Notes |
|---|------|--------|-------|
| TH.1 | Fix 8 failing upload unit tests | ✅ Done | Added `reset_storage()` to `async_client` fixture in conftest.py. Storage singleton now picks up patched `data_dir` tmpdir. All 8 previously-failing upload tests pass. |
| TH.2 | Cookie Secure flag configurable | ✅ Done | Added `cookie_secure: bool` to Settings. auth.py reads `settings.cookie_secure` at call time (removed hardcoded `_COOKIE_SECURE = False`). docker-compose.selfhosted.yml sets `COOKIE_SECURE=true`. 2 new tests. |
| TH.3 | Dashboard Redis cache | ✅ Done | New `app/core/cache.py` with async Redis cache helpers. Dashboard endpoint: cache-first with 30s TTL, per-user key. Upload endpoint invalidates user's dashboard cache. 3 new tests. |
| TH.4 | CI coverage enforcement | ✅ Done | Raised `--cov-fail-under` from 70% to 75%. Added `--cov-report=xml:coverage.xml`. Added `actions/upload-artifact@v4` step for coverage report. |
| TH.5 | E2E Settings + Dark Mode tests | ✅ Done | New `settings.spec.ts` with 4 tests: navigate to settings, sections render, dark mode toggle, dark mode persistence across reload. |

**Tests:** 934 unit + 232 golden + 34 E2E = ~1200 total tests.

## Production Launch Readiness

| # | Task | Status | Notes |
|---|------|--------|-------|
| PLR.1 | Deep Health Checks | ✅ Done | `/health/live` (liveness) + `/health/ready` (DB+Redis check, returns 503 when degraded). Updated all compose healthchecks + ECS. `check_db_connectivity()` + `check_redis_connectivity()` helpers. 6 new tests. |
| PLR.2 | Production Logging | ✅ Done | structlog renderer selection: `LOG_FORMAT=json|console|auto` (auto=JSON when not TTY). AccessLogMiddleware logs method/path/status/duration_ms (skips health endpoints). 5 new tests. |
| PLR.3 | DB & Startup Safety | ✅ Done | `pool_pre_ping=True`, configurable `db_pool_size`/`db_max_overflow`/`db_pool_recycle`. JWT secret startup check (rejects default in SaaS mode). Graceful shutdown (`--timeout-graceful-shutdown 30` + `stop_grace_period: 35s`). `worker_max_tasks_per_child=100`. 3 new tests. |
| PLR.4 | Security Hardening | ✅ Done | HSTS header (when `cookie_secure=true`). CSP in nginx.conf. Conditional OpenAPI (`openapi_enabled` config). Auth rate limits tightened: register 3/min, forgot-password 3/min, reset-password 3/min. `scripts/preflight-check.sh` validates .env. 5 new tests. |
| PLR.5 | Automated Backups + Restore | ✅ Done | Celery beat `daily-backup` task (configurable hour, `backup_enabled` flag). Dump integrity verification in backup.sh. `scripts/restore.sh` with guided restore. `make restore`, `make preflight`. Deployment docs updated. |

**Tests:** 953 unit + 232 golden + 34 E2E = ~1219 total tests (24 new).

## OAuth + SaaS Launch Prep

| # | Task | Status | Notes |
|---|------|--------|-------|
| OA.1 | OAuth Client Factory | ✅ Done | `core/oauth.py`: Authlib `AsyncOAuth2Client` helpers, Google+GitHub provider configs, `OAuthUserInfo` dataclass, Redis state storage (10min TTL), `build_authorize_url`/`exchange_code_for_token`/`fetch_userinfo`. Config: `oauth_redirect_base_url`. |
| OA.2 | OAuth Redirect Endpoint | ✅ Done | `GET /api/auth/oauth/{provider}`: validates provider, generates CSRF state, stores in Redis, returns 302 to provider consent screen. Scopes: Google (openid email profile), GitHub (read:user user:email). |
| OA.3 | OAuth Callback Endpoint | ✅ Done | `GET /api/auth/oauth/{provider}/callback`: validates state from Redis, exchanges code for token, fetches userinfo, calls `create_or_link_oauth`, sets auth cookies, redirects to `/`. Error paths: invalid state→403, no email→400, provider error→redirect to `/login?error=oauth_failed`. |
| OA.4 | Avatar URL in OAuth Service | ✅ Done | `create_or_link_oauth()` now accepts `avatar_url` param. Sets avatar on new users, fills missing avatar on existing users (won't overwrite existing). |
| OA.5 | Frontend OAuth Improvements | ✅ Done | `OAuthButtons.tsx`: CSS theme vars (border-border, bg-surface, text-text), loading spinner, provider SVG icons. `LoginPage.tsx`: reads `?error=` query param, displays OAuth error message. |
| OA.6 | OAuth Tests | ✅ Done | 40 new tests: `test_oauth.py` (20 — state, config, URLs, userinfo), `test_auth_oauth.py` (13 — redirect, callback endpoints), `test_user_service_oauth.py` (7 — service logic). All pass, no regressions. |

**Tests:** 993 unit + 232 golden + 34 E2E = ~1259 total tests (40 new).

## Per-User AI Credentials

| # | Task | Status | Notes |
|---|------|--------|-------|
| PU.1 | settings_service: claude_cli_credentials key + get_user_agent_config() | ✅ Done | New ALLOWED_KEY with JSON validation (claudeAiOauth.accessToken/refreshToken). _AGENT_CONFIG_KEYS set. Async helper returns AI-related settings or None. |
| PU.2 | Agent factory user-aware | ✅ Done | get_agent(user_settings=dict) routes credentials to adapter constructors. Parses CLI credentials JSON for ClaudeCodeAdapter. Falls back to system defaults. |
| PU.3 | ClaudeCodeAdapter per-user credential files | ✅ Done | Temp dir with .credentials.json, CLAUDE_CONFIG_DIR env var on subprocess. Reads back refreshed tokens. Cleans up in finally block. |
| PU.4 | Pipeline stages fetch per-user settings | ✅ Done | classify, summarize, assets, courseops_task, concept_service, qa, chat_service — all lazy-import get_user_agent_config before get_agent(). Credential refresh persisted after CLI calls. |
| PU.5 | POST /settings/test-ai endpoint | ✅ Done | Validates user's AI credentials via classify_lecture test prompt. Returns status/backend/message or 502 on failure. TestAIResponse schema. |
| PU.6 | Frontend credential input UI | ✅ Done | SettingsPage: CLI credentials textarea with status badges, Anthropic API key field, Test Connection button with result display. TypeScript types updated. |
| PU.7 | Unit tests | ✅ Done | 29 new tests (factory routing, credential validation, temp file flow, test-ai endpoint). Fixed 7 existing tests (chat_service, chat_streaming, assets). 1021 unit + 285 golden = 1306 total. |

## Frontend Rework (Streams A–F)

Full stream log: `docs/frontend-rework/PROGRESS.md`. Design brief and plan: `docs/frontend-rework/`.

| # | Stream | Status | Notes |
|---|--------|--------|-------|
| FR.A | Design system, tokens, vitest | ✅ Done | Nordic Calm dark-anchored token layer (`--t-*` + `@theme inline`), 11 UI primitives with tests, vitest infra, color-guard CI check. |
| FR.B | Error layer | ✅ Done | Typed API error taxonomy, route error boundaries, persistent study-write queue, connectivity banner, SSE resume. |
| FR.C | Shell, IA, ⌘K, Ask | ✅ Done | Activity-group nav (Sidebar/MobileNav), command palette + global shortcuts, `useTabRouting`, QA merged into /ask. |
| FR.D | Screen redesigns (D1–D11) | ✅ Done | Home widgets, Study Hub w/ Plan tab, Week view + reclassify, Course management, Pipeline console, Review inbox, Knowledge, Analytics + readiness, Settings sub-routes, Auth, Admin/Achievements/CourseOps. |
| FR.E | Backend features (TDD) | ✅ Done | 7 new endpoint groups: global search, notification inbox, study plan, quick capture, exam readiness, artifact reclassify, course management (rename/archive/delete/merge). Documented in `docs/api.md`. |
| FR.F | Hardening | ✅ Done | Color allowlist emptied and removed (guard fails on any raw palette class). 10 new Playwright specs incl. axe a11y gate (6 pages × 2 themes) and failure-mode tests (forced 500s, offline). Bundle budget (500KB) in CI. Fixed: dark-theme CSS cascade bug, WCAG AA contrast tokens, nested-interactive session rail, sonner toast palette. Suite: 1136 backend, 380 vitest, 59 e2e passed / 5 data-skips. |

## Issues & Blockers

| Date | Issue | Status | Resolution |
|------|-------|--------|------------|
| | | | |

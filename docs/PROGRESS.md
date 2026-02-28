# StudyAIO — Progress Tracker

> **Current Milestone:** 1 — Foundation & Pipeline (No UI)
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
| 2.1 | FastAPI endpoints (upload, courses, summaries, review) | ⬜ Not Started | |
| 2.2 | React project setup (Vite, Tailwind, Router, Query) | ⬜ Not Started | |
| 2.3 | Dashboard page | ⬜ Not Started | |
| 2.4 | Upload page | ⬜ Not Started | |
| 2.5 | Course page | ⬜ Not Started | |
| 2.6 | Week view | ⬜ Not Started | |
| 2.7 | Review Inbox page | ⬜ Not Started | |
| 2.8 | Navigation (sidebar + mobile) | ⬜ Not Started | |
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
| 2026-02-28 | UI service behind `ui` profile | Not needed for Milestone 1; won't start by default |
| 2026-02-28 | uuid7 pip package imports as uuid_extensions | Fixed import in core/utils.py |
| 2026-02-28 | Added alembic/ volume mount to docker-compose.yml | So migrations persist on host, not just in image |

## Issues & Blockers

| Date | Issue | Status | Resolution |
|------|-------|--------|------------|
| | | | |

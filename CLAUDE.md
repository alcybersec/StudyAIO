# StudyAIO — Claude Code Instructions

> Full PRD: `docs/PRD.md` | Architecture: `docs/architecture.md`

## Project Summary

StudyAIO is a local-first, dockerized AI study workspace. It automates the journey from raw lecture files (PDF, DOCX, PPTX) to organized, searchable, exam-ready study materials. Modular monolith architecture: FastAPI + Celery + React + Postgres (pgvector) + Redis, all in Docker Compose.

## Current Milestone

**Milestone 1 — Foundation & Pipeline (No UI)**

Track progress in `docs/PROGRESS.md`. Update it after completing each task.

## Tech Stack

- **Backend:** Python 3.12, FastAPI, Celery, SQLAlchemy 2.0 (async), Alembic
- **Frontend:** React 18, Vite, Tailwind CSS, React Query, React Router
- **Database:** PostgreSQL 16 + pgvector extension
- **Queue:** Redis 7
- **AI Runtime (v1):** Claude Code CLI via subprocess (Max plan)
- **Containerization:** Docker Compose
- **Testing:** pytest, pytest-asyncio, httpx (API tests)

## Commands

```bash
# Docker
docker compose up -d                    # Start all services
docker compose down                     # Stop all services
docker compose logs -f api              # Tail API logs
docker compose logs -f worker           # Tail worker logs
docker compose exec db psql -U studyaio # Connect to database

# Backend (inside services/app/)
pip install -r requirements.txt         # Install dependencies
alembic upgrade head                    # Run DB migrations
alembic revision --autogenerate -m "description"  # Create migration
pytest                                  # Run all tests
pytest tests/unit                       # Unit tests only
pytest tests/integration                # Integration tests
pytest -x -v                            # Stop on first failure, verbose

# Frontend (inside services/ui/)
npm install                             # Install dependencies
npm run dev                             # Start dev server
npm run build                           # Production build
npm run lint                            # Lint check

# Convenience (from repo root)
make up                                 # docker compose up -d
make down                               # docker compose down
make test                               # Run all backend tests
make migrate                            # Run migrations
make shell                              # Open bash in API container
make db                                 # Open psql shell
make logs                               # Tail all service logs
```

## Repo Structure

```
studyaio/
├── services/
│   ├── app/                    # FastAPI + Celery monolith
│   │   ├── app/
│   │   │   ├── main.py         # FastAPI app factory
│   │   │   ├── config.py       # Pydantic Settings from env
│   │   │   ├── worker.py       # Celery app factory
│   │   │   ├── api/            # FastAPI routers
│   │   │   ├── models/         # SQLAlchemy ORM models
│   │   │   ├── pipeline/       # Pipeline stage tasks (Celery)
│   │   │   ├── agents/         # AgentAdapter interface + impls
│   │   │   ├── extractors/     # PDF/DOCX/PPTX parsers
│   │   │   ├── services/       # Business logic layer
│   │   │   └── core/           # DB, Redis, shared utilities
│   │   ├── prompts/            # AI prompt templates
│   │   ├── tests/
│   │   ├── alembic/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── ui/                     # React frontend
│       ├── src/
│       ├── Dockerfile
│       └── package.json
├── infra/
│   ├── docker-compose.yml
│   └── db/init.sql
├── data/                       # Docker volumes (gitignored)
├── scripts/                    # Utility scripts
├── tests/fixtures/             # Test files (small PDFs, etc.)
├── docs/
│   ├── PRD.md
│   ├── PROGRESS.md
│   └── architecture.md
├── new_lectures/               # v0 compatibility: drop zone
├── raw_lectures/               # v0 compatibility: organized files
├── lectures_summary/           # v0 compatibility: generated summaries
├── CLAUDE.md                   # This file
├── Makefile
└── .env.example
```

## Architecture Rules

1. **Modular monolith.** One Python app with clear internal module boundaries. Do NOT create separate microservices. The Celery worker runs the same codebase as the API.

2. **Database is source of truth.** All entities live in Postgres. Files on disk (data/ volumes) are blob storage only. Never read filesystem to determine state — query the database.

3. **Agent adapter pattern.** All AI calls go through `app/agents/base.py:AgentAdapter`. v1 implements `ClaudeCodeAdapter` that shells out to `claude -p`. Never call Claude directly from pipeline stages — always go through the adapter.

4. **Pipeline as Celery chain.** Each pipeline stage is a separate Celery task. Stages are chained: ingest → classify → extract → summarize → index → assets. Each stage is independently retryable.

5. **Review Inbox, not blocking.** When confidence is low, create a `ReviewItem` and set artifact status to `waiting_review`. Never block the pipeline for other files. Never silently guess high-stakes fields.

6. **Idempotent everything.** Same file uploaded twice = no-op (SHA-256 dedup). Same course+week summarized again = version increment, not duplicate. Chunks use stable IDs for upsert.

## Coding Conventions

### Python

- **Python 3.12+** — use modern syntax (type unions with `|`, etc.)
- **Type hints on all functions** — parameters and return types
- **Async by default** — FastAPI endpoints are `async def`, use `asyncio` for subprocess calls
- **Pydantic v2** for all request/response schemas and settings
- **SQLAlchemy 2.0 style** — mapped_column, DeclarativeBase, async sessions
- **UUID primary keys** — use `uuid7()` for time-sortable IDs
- **f-strings** for string formatting, never `.format()` or `%`
- **Logging** — use `structlog` with structured key-value pairs, never print()
- **Imports** — stdlib first, then third-party, then local. Use absolute imports.
- **No wildcard imports** — always explicit
- **Docstrings** — Google style on all public functions and classes
- **Constants** — UPPER_SNAKE_CASE, defined in config.py or module-level
- **Error handling** — custom exception classes in `app/core/exceptions.py`, caught at API layer

### Naming

- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions/variables: `snake_case`
- API routes: `kebab-case` URLs (`/review-items`, not `/review_items`)
- Database tables: `snake_case` plural (`lecture_artifacts`, `review_items`)
- Environment variables: `UPPER_SNAKE_CASE` prefixed with `STUDYAIO_` where ambiguous

### File Organization

- One SQLAlchemy model per file in `app/models/`
- One FastAPI router per resource in `app/api/`
- One Celery task per pipeline stage in `app/pipeline/`
- Business logic goes in `app/services/`, NOT in API routes or Celery tasks
- API routes are thin: validate input → call service → return response
- Celery tasks are thin: call service/extractor/agent → persist result → enqueue next stage

### Tests

- Test files mirror source structure: `app/pipeline/classify.py` → `tests/unit/pipeline/test_classify.py`
- Use `pytest` fixtures for database sessions, test clients, sample data
- Unit tests: no external deps (mock the database, mock Claude)
- Integration tests: use real Postgres + Redis via testcontainers
- Golden tests: verify structure of outputs, not exact AI-generated text
- Every new feature must include tests. Do not skip tests to save time.

### Docker

- Dockerfiles use multi-stage builds where beneficial
- Pin base image versions (e.g., `python:3.12-slim`, not `python:3-slim`)
- `.dockerignore` excludes: `data/`, `__pycache__/`, `.git/`, `node_modules/`
- All config via environment variables with defaults in `app/config.py`

## Data Model (Quick Reference)

Core tables: `courses`, `lecture_artifacts`, `extractions`, `summaries`, `chunks`, `flashcards`, `quiz_questions`, `review_items`, `pipeline_runs`

Key relationships:
- Course 1→* LectureArtifact 1→1 Extraction
- Course 1→* Summary (per week, unique on course_id+week)
- LectureArtifact 1→* Chunk (with pgvector embedding)
- LectureArtifact 1→* Flashcard, QuizQuestion
- ReviewItem references any entity via entity_type + entity_id

See `docs/PRD.md` section 10 for full column definitions.

## AI Prompts

All prompts live in `services/app/prompts/` as `.txt` files. When modifying prompts:
- Keep the existing structure/sections
- Test with at least 2 different lecture files
- Document what changed and why in a comment at the top of the prompt file
- Prompts use Jinja2-style `{{ variable }}` placeholders

## Pipeline Stages Reference

| Stage | Celery Task | Input | Output | Creates ReviewItem? |
|-------|------------|-------|--------|-------------------|
| 0: Ingest | `pipeline.ingest.ingest_file` | File path | LectureArtifact | No |
| 1: Classify | `pipeline.classify.classify_artifact` | artifact_id | Updated artifact | Yes (if low confidence) |
| 2: Extract | `pipeline.extract.extract_artifact` | artifact_id | Extraction record | No |
| 3: Summarize | `pipeline.summarize.summarize_week` | artifact_id | Summary record | No |
| 4: Index | `pipeline.index.index_artifact` | artifact_id | Chunk records | No |
| 5: Assets | `pipeline.assets.generate_assets` | artifact_id | Flashcards + Quizzes | No |

## Summary Format

Every summary must include these sections in this order:
1. `# <Course> — Week <N>: <Topic>` (title)
2. `## Key Concepts`
3. `## Definitions` (table: Term | Definition)
4. `## Code Examples` (if applicable)
5. `## Diagrams & Figures` (embedded images with captions)
6. `## Potential Exam Topics`
7. `## Summary` (2-3 paragraph overview)
8. Footer with metadata: sources, version number

## Important Warnings

- **NEVER delete data/ directory contents** — these are user uploads and generated content
- **NEVER commit .env files** — use .env.example as template
- **NEVER hardcode file paths** — use config.py settings
- **NEVER call Claude Code CLI directly from API routes** — always through agent adapter, always from Celery worker
- **NEVER use print() for logging** — use structlog
- **NEVER skip migrations** — always create Alembic migrations for schema changes
- **NEVER store secrets in CLAUDE.md or code** — environment variables only

## v0 Compatibility

The existing slash commands (`/sort_lectures`, `/summarize_lectures`) must continue to work. They operate on `new_lectures/`, `raw_lectures/`, and `lectures_summary/` directories. The new application uses `data/` for its storage. These are separate systems that can coexist.

## When You're Unsure

- Check `docs/PRD.md` for detailed specifications
- Check `docs/PROGRESS.md` for what's been built
- If a design decision isn't covered by the PRD, create a `TODO` comment and flag it — don't guess
- Prefer simple solutions over clever ones
- When in doubt, add a test

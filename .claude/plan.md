# Plan: Initialize Git, Create GitHub Repo, Assess Status & Plan Next Steps

## Step 1: Initialize Git Repository

- Run `git init` in the project root
- Create a comprehensive `.gitignore` (Python, Node, Docker, data volumes, env files, lecture files)
- Stage all existing files (CLAUDE.md, Makefile, docs/, lecture_manager/ v0 code, .mcp.json)
- Create initial commit

## Step 2: Create GitHub Repository & Connect

- Use `gh repo create alcybersec/study-helper-project --private --source=. --push` to create the repo and push in one step
- This creates a private repo on your GitHub, sets the remote, and pushes the initial commit

## Step 3: Current Project Status Assessment

**What exists today:**
- `CLAUDE.md` — Full project instructions for Claude Code
- `docs/PRD.md` — Complete 1,500-line PRD (approved for development)
- `docs/PROGRESS.md` — Progress tracker (all tasks "Not Started")
- `Makefile` — Docker/test/migration commands (ready to use)
- `lecture_manager/` — v0 system with:
  - `.claude/commands/` — sort_lectures.md, summarize_lectures.md slash commands
  - `raw_lectures/` — organized lecture files (CSIT302: 13 files, CSIT314: 15 files)
  - `lectures_summary/` — generated summaries (CSIT302: 8 weeks, CSIT314: 10 weeks)
  - `scripts/extract_text.py` — text extraction utility
  - `new_lectures/` — empty drop zone
- `.mcp.json` — empty MCP config

**What does NOT exist yet (needed for Milestone 1):**
- `services/app/` — entire backend (FastAPI, Celery, models, pipeline, agents, extractors)
- `services/ui/` — entire frontend (React, Vite, Tailwind)
- `infra/docker-compose.yml` — Docker Compose orchestration
- `infra/db/init.sql` — database initialization
- `.env.example` — environment variable template
- `alembic/` — database migrations
- `tests/` — test suite and fixtures
- `data/` — Docker volume directories
- `scripts/` — import/seed/reset scripts
- `docs/architecture.md` — architecture documentation

**Current Milestone:** 1 — Foundation & Pipeline (No UI)
**Status:** Not started — zero of 10 tasks complete

## Step 4: Recommended Next Steps (Milestone 1 Execution Order)

After git/GitHub setup, the work follows this sequence:

### 4a. Task 1.1: Repo Structure + Docker Compose + Config
- Create the full directory scaffold (`services/app/app/`, `services/ui/`, `infra/`, `data/`, `scripts/`, `tests/`)
- Create `infra/docker-compose.yml` with all 5 services (ui, api, worker, db, redis)
- Create `infra/db/init.sql` (pgvector extension setup)
- Create `.env.example`
- Create `services/app/Dockerfile` (Python 3.12-slim, multi-stage)
- Create `services/app/requirements.txt` (FastAPI, Celery, SQLAlchemy, Alembic, structlog, etc.)
- Create `services/app/app/__init__.py`, `main.py` (app factory), `config.py` (Pydantic Settings), `worker.py` (Celery factory)
- Create `services/app/app/core/database.py`, `redis.py`, `exceptions.py`, `utils.py`
- Create `.dockerignore`
- Set up Alembic (alembic init, configure for async)
- Verify `docker compose up` starts all services cleanly

### 4b. Task 1.2: Database Schema + Migrations
- Create all SQLAlchemy models (9 tables: courses, lecture_artifacts, extractions, summaries, chunks, flashcards, quiz_questions, review_items, pipeline_runs)
- Generate Alembic migration
- Verify schema applies cleanly against Postgres

### 4c. Tasks 1.3-1.8: Pipeline stages (each depends on the previous)
- File extractors → Ingest → Classify → Extract → Summarize → Orchestrator

### 4d. Tasks 1.9-1.10: Tests + v0 import script

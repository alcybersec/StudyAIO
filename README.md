# StudyAIO

[![CI](https://github.com/alcybersec/StudyAIO/actions/workflows/ci.yml/badge.svg)](https://github.com/alcybersec/StudyAIO/actions/workflows/ci.yml)

A local-first, fully dockerized AI study workspace that turns raw university lecture files (PDF, DOCX, PPTX) into organized, searchable, exam-ready study materials.

## Features

- **6-stage processing pipeline** — Ingest, classify, extract, summarize, index, and generate study assets automatically via Celery task chains
- **Smart classification** — AI identifies course code, week number, and title from file contents; routes low-confidence results to a review inbox
- **Rich summaries** — Generates structured markdown summaries with key concepts, definitions, code examples, and exam topics per course week
- **Semantic search & Q&A** — Ask questions about your lectures with source citations backed by pgvector embeddings
- **Flashcards & quizzes** — Auto-generated flashcards with flip/shuffle and MCQ/short-answer quizzes with scoring
- **Real-time progress** — SSE-powered pipeline progress tracking in the browser
- **Review inbox** — Human-in-the-loop for low-confidence AI decisions with suggestion buttons and manual override

## Architecture

```mermaid
graph TB
    subgraph Browser
        UI[React + Vite + Tailwind]
    end

    subgraph Docker Compose
        API[FastAPI API Server]
        Worker[Celery Worker]
        DB[(PostgreSQL + pgvector)]
        Redis[(Redis)]
    end

    subgraph External
        Claude[Claude Code CLI]
    end

    UI -->|REST + SSE| API
    API -->|async sessions| DB
    API -->|pub/sub| Redis
    Worker -->|task queue| Redis
    Worker -->|async sessions| DB
    Worker -->|subprocess| Claude
    Worker -->|embeddings| ST[sentence-transformers]
```

### Pipeline Flow

```mermaid
graph LR
    A[Ingest] --> B[Classify]
    B --> C[Extract]
    C --> D[Summarize]
    D --> E[Index]
    E --> F[Assets]

    B -.->|low confidence| R[Review Inbox]
    R -.->|resolved| C
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, Celery, SQLAlchemy 2.0 (async), Alembic |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS v4, React Query, React Router |
| Database | PostgreSQL 16 + pgvector |
| Queue | Redis 7 |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| AI Runtime | Claude Code CLI via agent adapter pattern |
| Infrastructure | Docker Compose |
| Testing | pytest (186 unit tests), pytest-asyncio |

## Quick Start

```bash
# Clone the repository
git clone https://github.com/alcybersec/StudyAIO.git
cd StudyAIO

# Copy environment configuration
cp .env.example .env

# Start all services
docker compose up -d

# Run database migrations
make migrate

# Access the application
# UI:  http://localhost:3000
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
```

## Development

```bash
make up          # Start all Docker services
make down        # Stop all services
make test        # Run all backend tests
make migrate     # Run Alembic migrations
make shell       # Open bash in API container
make db          # Open psql shell
make logs        # Tail all service logs
```

## Testing

```bash
# Run all 186 unit tests
make test

# Run specific test modules
docker compose exec api pytest tests/unit/pipeline -v
docker compose exec api pytest tests/unit/api -v

# Stop on first failure
docker compose exec api pytest tests/unit -x -v
```

## Project Structure

```
studyaio/
├── services/
│   ├── app/                    # FastAPI + Celery backend
│   │   ├── app/
│   │   │   ├── api/            # REST endpoints (17 routes)
│   │   │   ├── agents/         # AI adapter pattern
│   │   │   ├── extractors/     # PDF/DOCX/PPTX parsers
│   │   │   ├── models/         # SQLAlchemy ORM (9 models)
│   │   │   ├── pipeline/       # Celery task stages (6)
│   │   │   └── services/       # Business logic layer
│   │   ├── prompts/            # Jinja2 AI prompt templates
│   │   └── tests/              # 186 unit tests
│   └── ui/                     # React frontend (6 pages)
│       └── src/
│           ├── pages/          # Dashboard, Course, Week, Upload, Q&A, Review
│           ├── components/     # Reusable UI components
│           ├── hooks/          # React Query + SSE hooks
│           └── api/            # Typed API client
├── infra/
│   ├── docker-compose.yml
│   └── db/init.sql
├── docs/
│   ├── PRD.md                  # Product requirements
│   ├── PROGRESS.md             # Milestone tracker
│   └── api.md                  # API reference
└── .github/workflows/ci.yml   # GitHub Actions CI
```

# StudyAIO — Design

Local-first, dockerized AI study workspace that turns raw lecture files (PDF, DOCX, PPTX) into organized, searchable, exam-ready study materials.

## Inherited documentation

These files are **authoritative** and are not restated or rewritten here. Read them directly:

- `docs/PRD.md`
- `docs/PRD_v2.md`
- `docs/architecture.md`

This file records design that those documents do not cover, and decisions taken after them.

## Module boundaries

Each role in `docs/strategy.md` §2 owns a boundary. The interfaces between them are recorded
in `docs/CONTRACTS.md`.

### architect

ADRs, contracts, module boundaries across the modular monolith.

_Design notes: to be written by `architect` as the boundary takes shape._

### backend

FastAPI routers, schemas, business-logic services, core infrastructure.

_Design notes: to be written by `backend` as the boundary takes shape._

### ai

Pipeline stages, agent adapters, extractors, prompts and evals.

_Design notes: to be written by `ai` as the boundary takes shape._

### data

SQLAlchemy models and Alembic migrations.

_Design notes: to be written by `data` as the boundary takes shape._

### frontend

React SPA — pages, components, hooks, i18n scripts, static assets.

_Design notes: to be written by `frontend` as the boundary takes shape._

### devops

Compose stacks, Dockerfiles, nginx, GitLab CI, infra and ops scripts.

_Design notes: to be written by `devops` as the boundary takes shape._

### qa

Integration, golden-structure and Playwright e2e tiers.

_Design notes: to be written by `qa` as the boundary takes shape._

### safety

Floors, threat model, auth-critical code.

_Design notes: to be written by `safety` as the boundary takes shape._

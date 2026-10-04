# ADR 0002 — Module boundaries of the modular monolith

**Status** Proposed · **Date** 2026-10-04 · **Kit version** 1.10.3

Proposed, not Accepted: the user's acceptance of these boundaries is a gate question (M31 gate,
Functional dimension, `docs/strategy.md` §5). This ADR records them; it cannot ratify them.

## Context

StudyAIO is one Python application (`services/app/app/`) served by two processes — the FastAPI API
and the Celery worker run the same code — plus a React SPA (`services/ui/`) and the Compose/infra
around them. `CLAUDE.md` "Architecture Rules" and `docs/architecture.md` "Module Boundaries"
describe the layers in prose. ADR 0001 then gave 8 roles exclusive ownership of paths
(`docs/strategy.md` §2). The two descriptions were written separately and nothing yet says how
the layers map onto the roles, nor which interfaces between them count as cross-role contracts.

The import graph as of `14c9bcc` (counted with
`grep -rhoE "^\s*(from|import) app\.[a-z_]+" app/<layer>`):

| Layer | Imports from |
|---|---|
| `core` | `core`, `config` only |
| `models` | `core`, `models` |
| `extractors` | `core`, `config` |
| `agents` | `core`, `config`, **`services.settings_service`** |
| `services` | `models`, `core`, `agents`, `services`, **`api.deps`** (1, `admin_service`) |
| `pipeline` | `services`, `models`, `core`, `agents`, `extractors`, `worker` |
| `api` | `core`, `models`, `services`, `agents`, `pipeline` (to enqueue) |

## Decision

**1. The layers and their owners.** Each layer is owned by exactly one role, as §2 already says.
This ADR adds no glob and moves none.

| Layer | Path under `services/app/` | Owner |
|---|---|---|
| api — thin routers, validate → service → respond | `app/api/**` | `backend` |
| services — business logic, stateless, take a session | `app/services/**` | `backend` |
| core — DB, cache, storage, auth, quota, exceptions | `app/core/**` | `backend` |
| templates — email HTML | `app/templates/**` | `backend` |
| models — ORM mapping only | `app/models/**` | `data` |
| migrations | `alembic/**` | `data` |
| pipeline — one Celery task per stage, thin | `app/pipeline/**` | `ai` |
| agents — `AgentAdapter`, backends, factory, embeddings | `app/agents/**` | `ai` |
| extractors — PDF/DOCX/PPTX parsers | `app/extractors/**` | `ai` |
| prompts, evals | `prompts/**`, `evals/**` | `ai` |
| ui | `services/ui/src/**`, `scripts/**`, `public/**` | `frontend` |
| infra — Compose, Dockerfiles, CI, `infra/`, `scripts/` | as listed in §2 | `devops` |
| test tiers | `tests/integration/**` and `tests/golden/**`; `tests/safety/**`; `tests/contracts/**` | `qa`, `safety`, `architect` |

**2. Dependency direction.** `core` ← `models` ← `services` ← `api`; `agents` and `extractors` sit
beside `services`; `pipeline` sits beside `api` as the worker's entry point and may enqueue only
through `pipeline.orchestrator` or a task's `.delay`. Nothing imports `api` or `pipeline` except
`api` (to enqueue) and the worker. Two existing imports run against this direction and are recorded
here, not ruled on:

- `agents → services.settings_service` (`get_effective_setting`, `BACKEND_REQUIRED_KEY`) in every
  backend and the factory: an `ai` module depends on a `backend` module for configuration.
- `services.admin_service → api.deps.DEFAULT_ADMIN_ID`: a service reaches up into the API layer.

Either is a candidate for a later task; neither is fixed by this ADR.

**3. What counts as a contract.** An interface is recorded in `docs/CONTRACTS.md` when its
provider and at least one consumer are owned by different roles. The first entry is
**`agents.AgentAdapter` v1** — the ABC in `app/agents/base.py`, its data types and
`agents.factory.get_agent`. It is chosen first because it is the one boundary that already
underpins a floor (floor 3), and because it crosses the `ai`/`backend` line in both directions:
pipeline stages (`ai`) and services and routes (`backend`) consume it. Each contract has a test
under `services/app/tests/contracts/` that parses the entry and fails when code and entry diverge.

**4. Paths no role owns.** `app/main.py`, `app/config.py`, `app/worker.py`, `app/cli.py`,
`tests/unit/**`, `tests/conftest.py`, `tests/fixtures/**`, the rootdir `conftest.py`, `pytest.ini`,
`pyproject.toml` and the requirements files are owned by no role, so the ownership guard admits any
role to them. That keeps unit tests next to whichever role writes the code under test, which is
intended; the app factory and worker factory being unowned is not deliberate and is flagged for the
Orchestrator rather than assigned here.

## Consequences

- The boundaries in this ADR equal `docs/strategy.md` §2 by construction. Changing a glob there
  means amending this ADR in the same change.
- Every new cross-role interface gets a `docs/CONTRACTS.md` entry and a contract test before it is
  built. The `AgentAdapter` test fails if a public member, a data-type field or a backend is
  added without bumping the entry, or if a new module starts importing the adapter without being
  listed as a consumer.
- Recording `AgentAdapter` as built surfaced that floor 3's second clause ("none is made from an API
  route") does not hold today: `api/qa.py`, `api/settings.py`, and chat and concept extraction via
  their services call the adapter in the API process. This ADR does not resolve that; it is raised
  to `safety` and the user, because floors change only by ADR with the user's agreement (§6).
- The two upward imports in Decision 2 stay until a task removes them. A contract test does not
  police import direction; adding such a check is a separate `architect` task if wanted.

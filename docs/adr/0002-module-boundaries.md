# ADR 0002 — Module boundaries of the modular monolith

**Status** Accepted (2026-10-09, by the user) · **Date** 2026-10-04 · **Revised** 2026-10-09 (M32-S1-ARCH-007) · **Kit version** 1.10.3

Accepted by the user on 2026-10-09 (M32-S1-ARCH-027), closing gate condition C1 of M32-S1
(carried from the M31 gate, Functional dimension, `docs/strategy.md` §5).

## Context

StudyAIO is one Python application (`services/app/app/`) served by two processes — the FastAPI API
and the Celery worker run the same code — plus a React SPA (`services/ui/`) and the Compose/infra
around them. `CLAUDE.md` "Architecture Rules" and `docs/architecture.md` "Module Boundaries"
describe the layers in prose. ADR 0001 gave 8 roles exclusive ownership of paths
(`docs/strategy.md` §2). The two descriptions were written separately; nothing said how the layers
map onto the roles, which interfaces between them are cross-role contracts, or which direction an
import may run.

Re-derived on 2026-10-09 at `e902a30` by walking every `.py` under `app/` with `ast` (function-local
imports included). Each row is the set of `app.*` units a unit imports; **bold** entries run
upward and are the only ones that do:

| Unit | Imports from |
|---|---|
| `config` | — |
| `core` | `config` |
| `models` | `core` |
| `extractors` | `config`, `core` |
| `agents` | `config`, `core`, **`services`** (`settings_service`, from the factory and all five backends) |
| `services` | `config`, `core`, `models`, `agents`, **`api`** (`admin_service` → `api.deps`) |
| `pipeline` | `config`, `core`, `models`, `services`, `agents`, `extractors`, `worker` |
| `api` | `config`, `core`, `models`, `services`, `agents`, `pipeline` (to enqueue) |
| `main` | `config`, `core`, `agents`, `api` |
| `worker` | `config`, `core` (tasks are registered by name in `include=`, not imported) |
| `cli` | `config`, `core`, `models`, `services` |

Since the first draft, ADR 0003 and ADR 0005 settled where AI calls may be made (floor 3), and
services now take `user_id` unconditionally (C6). Neither moved a layer edge.

## Decision

**1. The layers and their owners.** Each layer is owned by exactly one role.

| Layer | Path under `services/app/` | Owner |
|---|---|---|
| api — thin routers, validate → service → respond | `app/api/**` | `backend` |
| services — business logic, stateless, take a session | `app/services/**` | `backend` |
| core — DB, cache, storage, auth, quota, exceptions | `app/core/**` | `backend` |
| templates — email HTML | `app/templates/**` | `backend` |
| entry points — app factory, settings, admin CLI | `app/main.py`, `app/config.py`, `app/cli.py` | `backend` (new, §4) |
| worker entry point — Celery app, beat schedule | `app/worker.py` | `ai` (new, §4) |
| models — ORM mapping only | `app/models/**` | `data` |
| migrations | `alembic/**` | `data` |
| pipeline — one Celery task per stage, thin | `app/pipeline/**` | `ai` |
| agents — `AgentAdapter`, backends, factory, embeddings | `app/agents/**` | `ai` |
| extractors — PDF/DOCX/PPTX parsers | `app/extractors/**` | `ai` |
| prompts, evals | `prompts/**`, `evals/**` | `ai` |
| ui | `services/ui/src/**`, `scripts/**`, `public/**` | `frontend` |
| infra — Compose, Dockerfiles, CI, `infra/`, `scripts/` | as listed in §2 | `devops` |
| test tiers | `tests/integration/**` and `tests/golden/**`; `tests/safety/**`; `tests/contracts/**` | `qa`, `safety`, `architect` |

**2. Dependency direction.** `config` ← `core` ← `models` ← `services` ← `api`. `agents` and
`extractors` sit on `core`, beside `models`; `services` may use `agents` (only at the request-time
call sites ADR 0003 and ADR 0005 enumerate — floor 3 is pinned by `safety`'s tier, not here).
`pipeline` sits beside `api` as the worker's entry point. Nothing imports `api`, `pipeline`,
`main` or `cli` except as the table below allows. `api` reaches `pipeline` only to enqueue
(`pipeline.orchestrator`, or a task's `.delay`).

The rule, as data. `tests/contracts/test_layer_direction_contract.py` reads this block and fails
when the code's upward imports differ from `KNOWN_EXCEPTIONS` in either direction — a new one, or a
listed one that has been fixed. A unit may always import itself.

```python
ALLOWED_IMPORTS = {
    "config": [],
    "core": ["config"],
    "models": ["config", "core"],
    "extractors": ["config", "core"],
    "agents": ["config", "core"],
    "services": ["config", "core", "models", "agents"],
    "pipeline": ["config", "core", "models", "services", "agents", "extractors", "worker"],
    "api": ["config", "core", "models", "services", "agents", "pipeline"],
    "main": ["config", "core", "models", "services", "agents", "api"],
    "worker": ["config", "core"],
    "cli": ["config", "core", "models", "services"],
}

KNOWN_EXCEPTIONS = [
    # R-002a — scheduled fix, §3.
    ("app.agents.factory", "app.services.settings_service"),
    ("app.agents.claude_code", "app.services.settings_service"),
    ("app.agents.anthropic_api", "app.services.settings_service"),
    ("app.agents.openai_adapter", "app.services.settings_service"),
    ("app.agents.zai_adapter", "app.services.settings_service"),
    ("app.agents.ollama_adapter", "app.services.settings_service"),
    # R-002b — scheduled fix, §3.
    ("app.services.admin_service", "app.api.deps"),
]
```

Removing a pair when its fix lands is maintenance and needs no amendment. Adding a pair, or
widening a row of `ALLOWED_IMPORTS`, is a change to this decision and needs an amending ADR.

**3. The two upward imports are scheduled fixes, not accepted exceptions (R-002).** Both are
cheap and neither has a reason to stay.

- **R-002a** `agents → services.settings_service`. What the adapters use — `get_effective_setting`
  (env defaults only, no session, no user) and `BACKEND_REQUIRED_KEY` — is static configuration,
  not business logic. Fix: `backend` moves it, with `_defaults`, into `app/core/` and keeps
  `settings_service` re-exporting it; then `ai` repoints the six imports. Two tasks, `backend`
  first. Owner of the risk until closed: `architect`.
- **R-002b** `services.admin_service → api.deps.DEFAULT_ADMIN_ID`. Fix: `backend` moves the
  constant into `app/core/` and has `api.deps` import it from there. One `backend` task; both
  files are `backend`'s.

Until they land, the pairs in `KNOWN_EXCEPTIONS` keep the test green and stop the list growing.

**4. Paths no role owned (R-003).** `app/main.py`, `app/config.py` and `app/cli.py` go to `backend`:
they are the API factory, the settings object every layer reads, and an admin CLI over `services`.
`app/worker.py` goes to `ai`: it is the Celery app whose `include=` and beat schedule name pipeline
tasks, and `pipeline` is its only importer. A new setting an `ai` module needs is therefore a
request to `backend` — `config.py` is shared by every layer and should have one writer.

Still owned by no role, deliberately: `tests/unit/**`, `tests/conftest.py`, `tests/fixtures/**`,
the rootdir `conftest.py`, `pytest.ini`, `pyproject.toml`, the requirements files and
`docs/CONTRACTS.md` (§8). Unit tests sit with whichever role writes the code under test.

**5. What counts as a contract.** An interface is recorded in `docs/CONTRACTS.md` when its
provider and at least one consumer are owned by different roles, and each entry has a test under
`services/app/tests/contracts/` that fails when code and entry diverge. Recorded so far:
`agents.AgentAdapter` v1 with `get_agent` (this ADR's first entry) and the embedding gateway
(ADR 0005). Layer direction is pinned by Decision 2's block above.

## Consequences

- The boundaries in this ADR equal `docs/strategy.md` §2 and `.claude/kit.yaml`. On acceptance the
  Orchestrator adds the four paths of §4 to both and re-renders the kit; R-003 closes with that
  change. Changing a glob there later means amending this ADR in the same change.
- R-002 stays open until the three tasks in §3 land; each removes its pairs from
  `KNOWN_EXCEPTIONS`, and the contract test fails if one is fixed but left listed.
- Every new cross-role interface gets a `docs/CONTRACTS.md` entry and a contract test before it is
  built.
- Floor 3's request-time AI calls, which the first draft raised as unresolved, are settled by
  ADR 0003 and ADR 0005; this ADR defers to them.
- The contract test checks `app.*` imports between units only. It does not see dynamic imports,
  Celery task names given as strings, or third-party SDK use; floor 3's own tier covers the last.

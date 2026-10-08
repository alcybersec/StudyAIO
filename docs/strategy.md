# StudyAIO — Strategy

The operating model. `docs/plan/README.md` holds current state; this file holds the rules and the
task graph.

## 1. Roles

The Orchestrator plans and dispatches and writes no implementation code. Each role below owns file
paths, exclusively.

## 2. Ownership map

| Role | Owns | Handoff extras |
|---|---|---|
| `architect` | `docs/adr/**`, `services/app/tests/contracts/**` | — |
| `backend` | `services/app/app/api/**`, `services/app/app/services/**`, `services/app/app/core/**`, `services/app/app/templates/**` | — |
| `ai` | `services/app/app/pipeline/**`, `services/app/app/agents/**`, `services/app/app/extractors/**`, `services/app/prompts/**`, `services/app/evals/**` | `PROMPT CHANGES:`, `EVAL DELTA:` |
| `data` | `services/app/app/models/**`, `services/app/alembic/**` | `MIGRATION:`, `PII COLUMNS:` |
| `frontend` | `services/ui/src/**`, `services/ui/scripts/**`, `services/ui/public/**` | `A11Y:`, `I18N:` |
| `devops` | `infra/**`, `scripts/**`, `docker-compose.yml`, `docker-compose.prod.yml`, `docker-compose.production.yml`, `docker-compose.selfhosted.yml`, `.gitlab-ci.yml`, `Makefile`, `services/app/Dockerfile`, `services/ui/Dockerfile`, `services/ui/nginx.conf` | `SERVICES:`, `RUNBOOK:` |
| `qa` | `services/app/tests/integration/**`, `services/app/tests/golden/**`, `services/ui/e2e/**` | `COVERAGE DELTA:` |
| `safety` | `services/app/tests/safety/**`, `docs/security/**` | `FLOOR DELTA:`, `VETO:` |

A task crossing a boundary is split, or routed through `architect`. Ownership globs do not overlap;
`kitgen verify` enforces that.

## 3. Test tiers

| Tier | Floor |
|---|---|
| unit | 75% |
| integration | 70% |
| floor | 95% |

Unit is 75%, matching the `--cov-fail-under=75` that `.gitlab-ci.yml` already enforced when the kit
was adopted (2026-10-04). Raising it is a task, not a profile edit.

Pragmatic TDD: test-first for logic, contracts, the data layer and anything under a floor;
test-after with fixtures for adapters and glue; e2e for UI. `test(red):` prefixes a failing-test
commit.

## 4. Branching

Trunk-based, one task per branch `task/<TASK-ID>-<slug>`, Conventional Commits. Commits use
`git commit --only <path>`. Parallel dispatch uses worktree isolation.

## 5. Gates

A gate is checked across five dimensions: **Functional**, **Tests**, **Floors**, **Operational**,
and the milestone's own additions. Verdicts: **PASS**, **CONDITIONAL** (each condition carries an
owner and a deadline task ID), **BLOCK**. A failed dimension blocks; no dimension is averaged away.

`safety` produces the Floors dimension and signs it APPROVE or VETO. A VETO is not
overridable by the Orchestrator.

A CONDITIONAL that survives two milestones is itself a finding and must be raised to the user, not
carried silently.

## 6. Floors — never regress

1. tenant isolation: an authenticated endpoint never returns or mutates another user's rows; every user-owned query filters on user_id
2. no secrets in the tree: no plaintext credentials, tokens or keys committed, and per-user AI credentials are never logged or returned by the API
3. AI only via the adapter: every AI call goes through a sanctioned gateway, either AgentAdapter obtained via `get_agent`, or, for embeddings, EmbeddingProvider obtained via `get_embedding_provider`; outside `app/agents/**` and `app/pipeline/**` (the Celery worker), each gateway is called only at the call sites enumerated in ADR 0003 (`get_agent`) and ADR 0005 (`get_embedding_provider`), and a new such call site requires amending the ADR that lists it *(amended 2026-10-04, ADR 0003, weakening agreed by the user; amended 2026-10-04, ADR 0005, embeddings in scope per the user's R-004 ruling. ADR 0005 accepted by the user 2026-10-04)*
4. user data is never lost: nothing deletes uploads or generated content under data/ except explicit account deletion and the explicit user-initiated deletes of the user's own items enumerated in ADR 0004, and dedup/re-summarize/asset regeneration never destroys prior versions or study history *(amended 2026-10-04, ADR 0004, per the user's R-007 ruling. Item deletes are admitted; re-summarize and regeneration are not relaxed, and the code is to be fixed. ADR 0004 accepted by the user 2026-10-04, amended on acceptance: merge `keep_source` keeps the overwritten target summary as a version)*

Floors are append-only. Removing or weakening one requires an ADR and the user's explicit agreement.

## 7. Observability

Every stage lands with counters, latency metrics and structured logs in the same task that
implements it — never as a follow-up — in paths that task's own role holds per §2. A shared metric
registry or log schema is an interface: record it in `docs/CONTRACTS.md` and ask its owner for
the field, rather than reaching into their tree.

## 8. Contracts

New or changed interfaces are recorded in `docs/CONTRACTS.md` **before** implementation,
with a version and a diff entry.

`docs/CONTRACTS.md` is owned by **no role** in §2, deliberately: contract-first means the
implementing role records the contract before building against it, and the ownership guard allows an
unowned path to any role. "Do not write what you do not own" in `/handoff` means *what another role
owns* — an unowned path crosses nobody's boundary.

## 9. Handoffs

Every task ends with a `/handoff` note. Evidence over prose: the test command and its last line. A
note without a pasted run is not evidence and the Orchestrator re-runs the tests itself.

## 10. Milestones

| ID | Name | Status |
|---|---|---|
| M31 | Maintenance | closed 2026-10-08 (CONDITIONAL; C1–C6 → M32) |
| M32 | Next feature | open |

## 11. Task graph

Task IDs follow `{milestone}-S{sprint}-{OWNER}-{nnn}`. **Only the open milestone is expanded here.** The
Orchestrator expands the next milestone's tasks at gate time; a graph written further ahead than the
work is invented work.

To expand a milestone: copy the `### M31` block's three parts (Entry conditions, Tasks, Gate
additions) above the Later-milestones list, remove its line from that list, and set its §10 Status
to `open`. §10 Status is derived from `docs/plan/README.md`, which is authoritative.

### M31 — Maintenance

**Entry conditions**

- [x] The user has reviewed `docs/PRD.md`, `docs/PRD_v2.md`, `docs/architecture.md` and this file.
- [x] The role roster in §2 is accepted.
- [x] The floors in §6 are accepted.
- [x] Each M0 row's assigned role owns somewhere its output sensibly belongs. Every row routes its
  write into a path that role already owns, so the ownership guard blocks nothing — but check the
  result reads sensibly: a role whose only paths are documentation has nowhere natural to put a test,
  and that is a sign the ownership map needs adjusting before dispatch rather than after.
- [x] `git@192.168.10.20:alcybersec/StudyAIO.git` is reachable and `glab` is authenticated.

Confirmed 2026-10-04. `architect` was given `services/app/tests/contracts/**` so that
M31-S1-ARCH-001 has somewhere to put its contract test.

**Tasks**

| ID | Owner | Outputs | Tests | Acceptance |
|---|---|---|---|---|
| M31-S1-ARCH-001 | `architect` | `docs/CONTRACTS.md` first entry; ADR for the module boundaries | contract test skeleton in a path `architect` owns per §2 | Every entry in `docs/CONTRACTS.md` names its consumers and the boundaries match §2. The user's acceptance of the boundaries is a gate question (§5, Functional), not a condition this task can satisfy on its own |
| M31-S1-DEVOPS-002 | `devops` | dev environment reproducible from a clean clone; `make test` runs | one trivial smoke test, in a path `devops` owns per §2 or an unowned path, so the suite is wired | A clean clone reaches a green run in one documented command; exit code 5 from an empty collection is a failure, not a pass |
| M31-S1-SAFETY-003 | `safety` | the floor test tier, in a path `safety` owns per §2, one test per floor in §6; a handoff line asking `devops` to wire it into CI | floor tier green | Each floor in §6 has at least one test that fails when it is violated |
| M31-S1-QA-004 | `qa` | tier thresholds from §3 as config in a path `qa` owns per §2 or an unowned path; a handoff line asking `devops` to enforce them in CI | coverage gate fails below floor | A deliberate coverage drop fails `make test` locally and, once M31-S1-DEVOPS-005 lands, in the pipeline |
| M31-S1-DEVOPS-005 | `devops` | the floor tier (M31-S1-SAFETY-003) and the coverage thresholds (M31-S1-QA-004) wired into `.gitlab-ci.yml` | a pipeline run shows both stages | A deliberate floor violation and a deliberate coverage drop each redden the pipeline |
| M31-S1-ARCH-006 | `architect` | ADR 0003 amending floor 3 (added 2026-10-04 on user agreement) | contract tests still green | Floor 3 reworded with an exact request-time allowlist; user agreement recorded |
| M31-S1-QA-007 | `qa` | integration tests under `services/app/tests/integration/**` raising integration-tier coverage from 43.52% to ≥ 70% (added 2026-10-04: user kept the 70 tier, R-006) | `make test-integration` with `--cov=app --cov-fail-under=70` green | Coverage ≥ 70% measured against real Postgres + Redis; tests assert behaviour, not just execute lines |
| M31-S1-DEVOPS-005c | `devops` | integration tier wired: `scripts/test-integration.sh` and the CI integration job run with `--cov=app --cov-fail-under=<integration tier from pyproject>` | a pipeline run shows the integration coverage line | A deliberate drop fails `make test-integration` and the CI integration job. Depends on M31-S1-QA-007 |
| M31-S1-BACKEND-008 | `backend` | fixes for floor violations V1–V4 (R-007) and test-ai error redaction (R-008), in `services/app/app/{api,services}/**` (added 2026-10-04 from SAFETY-003) | the 4 red floor tests in `tests/safety` turn green with no edit to `tests/safety/**`; unit tests for each fix; `make test` green | `pytest tests/safety` → 0 failed (strict xfails remain until the user rules) |
| M31-S1-SAFETY-009 | `safety` | review of BACKEND-008; prune fixed inventory entries (added 2026-10-04) | `tests/safety` | Each fix APPROVE or a red test naming the hole |
| M31-S1-BACKEND-010 | `backend` | redact the user's stored credentials from provider errors returned/logged at `POST /api/qa/ask`, `chat_service.send_message`, `chat_service.stream_message` (added 2026-10-04 from SAFETY-009) | `test_floor2_provider_error_never_echoes_a_stored_credential` green with no edit to `tests/safety/**` | `pytest tests/safety` → 0 failed |

**Gate additions:** the floor tier must be non-empty and green, and every floor in §6 must map to a
named test.

### M32 — Next feature

**Entry conditions**

- [x] M31 gate accepted by the user (2026-10-08, CONDITIONAL; `docs/gates/M31/summary-rerun-2026-10-08.md`).
- [ ] The user names the feature; the Orchestrator then adds its tasks here (S2 onward).

**Tasks** — S1 carries the M31 gate conditions. A condition still open at the M32 gate survives a
second milestone and becomes a BLOCK.

| ID | Owner | Outputs | Tests | Acceptance |
|---|---|---|---|---|
| M32-S1-BACKEND-001 | `backend` | C2a: `delete_user_account` deletes in FK-safe order (course documents/assessments before courses) | `test_account_deletion_courseops.py` strict xfails turn XPASS (markers → `qa`) | `DELETE /auth/account` and admin delete succeed for a user with course documents and assessments |
| M32-S1-BACKEND-002 | `backend` | C2b: billing free-tier constants, MFA-disable 400, achievement `title`, gcal RFC 3339 `timeMin` | the 4 remaining R-016 strict xfails turn XPASS | Each pinned integration test passes; no new xfail |
| M32-S1-QA-003 | `qa`, `devops` | C3: the 10 conditional e2e skips made deterministic in CI (seed data + auth mode), or each accepted on record | `e2e-tests` job | `e2e-tests` reports 0 skipped, or each remaining skip is listed with a reason the user accepted |
| M32-S1-SAFETY-004 | `safety` | C4: pin the global `AgentError` handler directly; F-2 stale `FLOORS.md` notes | floor tier | The pin fails with the handler fix reverted |
| M32-S1-BACKEND-005 | `backend`, `architect` | C5 / R-020: account purge removes summary and summary-version blobs of all the user's courses, including already-deleted ones; ADR 0004 #1 wording corrected | floor-4 pin from `safety` | After account deletion no blob of the user's remains under `summaries/` |
| M32-S1-BACKEND-006 | `backend`, `safety` | C6 / R-021: `user_id` required on scoped service functions, or the floor check fails on a `None` default | floor tier | A scoped function with `user_id=None` default reddens the floor tier |
| M32-S1-ARCH-007 | `architect` | C1: ADR 0002 accepted or amended per the user's review | contract tests | ADR 0002 Status is Accepted |

**Gate additions:** C1–C6 closed; floor tier non-empty and green; 0 strict xfails pinning R-016.

### Later milestones (outline only, not yet scoped)

_none yet_

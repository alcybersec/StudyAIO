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
| `backend` | `services/app/app/api/**`, `services/app/app/services/**`, `services/app/app/core/**`, `services/app/app/templates/**`, `services/app/app/main.py`, `services/app/app/config.py`, `services/app/app/cli.py` | — |
| `ai` | `services/app/app/pipeline/**`, `services/app/app/agents/**`, `services/app/app/extractors/**`, `services/app/prompts/**`, `services/app/evals/**`, `services/app/app/worker.py` | `PROMPT CHANGES:`, `EVAL DELTA:` |
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
| M32 | Safe to grow (audit S1 + security/money/integrity S2) | open |
| M33 | Trust and retention (audit AI quality, usage, onboarding, strategic bet) | not started |

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

### M32 — Safe to grow

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

**S4 — audit remediation** (source: [`docs/audits/2026-10-10-product-audit.md`](audits/2026-10-10-product-audit.md);
the user's direction for M32, logged 2026-10-10). Quick wins first, in the audit's order; new-feature work
is paused until S4 wave 1 closes. Finding IDs are the audit's.

*Wave 1 — S1 and quick wins (audit §4)*

| ID | Owner | Finding | Acceptance |
|---|---|---|---|
| M32-S4-BACKEND-001 | `backend` (+`safety` pin) | SEC-01: `claude_code_path` (and `claude_model` unless needed) user-settable → server executes it | Both keys removed from user `ALLOWED_KEYS`, operator-only; stored values ignored; floor pin that no user setting reaches an exec path |
| M32-S4-AI-002 | `ai` (+`safety`) | AGENT-01 remainder: temp cwd (not `/app`), honour `--model`, non-root, system prompt | CLI runs in an empty per-call cwd, as a non-root uid, with the configured model; pins for each |
| M32-S4-BACKEND-003 | `backend` | AI-05: `/api/qa/ask` citations from model output | Reuses chat's deterministic `build_sources`; every `[n]` maps to a retrieved chunk |
| M32-S4-BACKEND-004 | `backend` (+`safety`) | SEC-03: SSRF via user `ollama_base_url` / `zai_base_url` | Private/link-local/loopback ranges refused (incl. after DNS resolution), or operator-only when not self-hosted |
| M32-S4-BACKEND-005 | `backend`, `ai` | PROD-03: reminders off by default twice; no day-2 trigger | New users opted in (opt-out), global flag on in prod config, day-2 nudge |
| M32-S4-AI-006 | `ai`, `frontend` | AI-04: streaming chat shows raw JSON | Stream plain text; structure attached at the end; no JSON in the UI |
| M32-S4-AI-007 | `ai`, `data` | AI-03: chunks exceed MiniLM's 256 word-piece limit; user-settable up to 5000 | ~200-token chunks, user setting capped, re-embed job for existing data (or a longer-context embedder, by ADR) |
| M32-S4-FRONTEND-008 | `frontend` | UX-06: Study hub tab bar overflows on phones | Scrolls horizontally at 375px; e2e at mobile width |
| M32-S4-BACKEND-009 | `backend` (+`safety`) | QUOTA-01 + COST-01 — **after the user decides PROD-08** | Every bypass route checks quota; non-zero global ceilings; chat/Q&A/stream/concepts record usage; `top_k` bounded; counter race fixed |

*Wave 2 — security, money and data-integrity S2 (M32)*

| ID | Owner | Finding | Acceptance |
|---|---|---|---|
| M32-S4-BACKEND-010 | `backend`, `data` (+`safety`) | SEC-06: per-user AI keys / Claude tokens plaintext in JSONB (R-033) | Encrypted at rest with a key from the environment; migration re-encrypts existing rows; floor-2 pins stay green |
| M32-S4-BACKEND-011 | `backend` | BILL-01: Stripe webhook no dedupe/ordering; `trialing` unmapped (R-034) | Idempotent by event id; out-of-order events can't downgrade; `trialing` mapped; integration tests |
| M32-S4-AI-012 | `ai` | TECH-04: transient AI error = permanent failure; no time limits; stuck items never recover | Retries with backoff for transient errors; per-stage time limits; a beat job requeues or fails stuck items visibly |
| M32-S4-AI-013 | `ai`, `backend` | TECH-05: concurrent summarize of the same week races | Per-(course, week) lock or serialisation; both artifacts succeed; integration test with two parallel uploads |
| M32-S4-DEVOPS-014 | `devops` | TECH-06: documented auto-backup can't run in the image; deploy migrates without a dump (R-028 fixed the order) | Backup runs in prod (verified on the VM); `deploy.sh` takes a DB dump before migrating |
| M32-S4-BACKEND-015 | `backend`, `devops` (+`safety`) | SEC-05: self-hosted default makes unauthenticated callers admin; Postgres/Redis published (R-035) | Secure-by-default self-host: explicit opt-in for single-user mode, no published DB/Redis ports |
| M32-S4-FRONTEND-016 | `frontend`, `backend` | UX-05: raw server/exception strings shown to users | User-facing errors are mapped messages; raw text only in logs |
| M32-S4-DEVOPS-017 | `devops`, `safety` | SEC-07: vulnerable deps (starlette, python-multipart, transformers, react-router) | Upgraded; a dependency audit step in CI |
| M32-S4-BACKEND-018 | `backend` | SEC-10: rate limits per process (2× looser) | Limits shared via Redis across processes |
| M32-S4-DEVOPS-019 | `devops` | SEC-11: unused Terraform with plaintext secrets, Redis without auth | Removed or fixed |
| M32-S4-QA-020 | `frontend`, `qa` | UX-08: non-semantic click targets; SSE `JSON.parse` unguarded | Semantic buttons/links; guarded parse; e2e |

**User decision before M32-S4-BACKEND-009:** PROD-08 free-tier limits (generous limits, or Pro for beta users).

**Gate additions:** C1–C6 closed; floor tier non-empty and green; 0 strict xfails pinning R-016. From the
audit: every S1 (SEC-01, AGENT-01) closed with a floor pin shown red on the hole; QUOTA-01/COST-01 enforced
on every AI-spending route with non-zero ceilings in prod; no open audit S2 in security, money or data
integrity (SEC-03, SEC-05, SEC-06, BILL-01, TECH-04, TECH-05, TECH-06); `safety` APPROVE.

### M33 — Trust and retention (outline; tasks cut at the M32 gate)

Source: `docs/audits/2026-10-10-product-audit.md`. Theme: make the AI measurably trustworthy and learn
whether people come back, before building more.

- **AI trust:** AI-07 (summary faithfulness, slide citations, no outside material), AI-10 (eval set beyond
  3 cases, evals in CI, user feedback on AI output), AI-06 (relevance floor; follow-up retrieval),
  AI-01 (per-backend model choice, no full-week re-summarise per upload, prompt caching), AI-12 (prompt/model
  version on rows; drop drifted inline prompts), AI-09 (structured output, retry on malformed replies).
- **Usage and retention:** PROD-10 (per-feature usage events, D7/D30), PROD-06 (onboarding; no empty
  dashboard), UX-01 (pipeline progress survives navigation), PROD-05 (edit/delete/add AI flashcards and quiz
  items), PROD-07 (course/week picker on upload).
- **Compliance:** SEC-08 (AI-processing disclosure/consent; no emails in logs).
- **Debt:** TECH-07 (async embedding; no DB connection across LLM calls), TECH-09 (separate queues),
  TECH-11 (type checker; easier integration tier; slimmer images), UX-02, UX-03, UX-04, UX-07, PROD-09
  (OCR, URL import), PROD-11 (README).
- **One strategic bet, chosen by the user at the M32 gate** (audit §5): trust as the wedge, weak-spot
  engine, shared course spaces (PROD-04), self-host/BYO-model, Arabic/RTL, or certification prep.
- **Validation track (audit §6), user-owned:** D7/D30 on the current users, fake-door Pro, shared-course
  seed, instructor interviews.

**Gate additions (draft):** summary faithfulness measured on ≥ 20 cases in CI with a baseline and a
non-regression threshold; Q&A and summary citations grounded and pinned; per-feature usage events live in
prod with a D7/D30 readout for the current users.

### Later milestones (outline only, not yet scoped)

_none yet_

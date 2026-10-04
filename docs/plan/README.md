# Dispatch State

**Owner.** Orchestrator. **Updated.** After every task completion and every gate.

Source of truth for "what is next". Subagents never edit this file; they emit handoff notes and the
Orchestrator updates here.

---

## Current milestone

**M31 — Maintenance.** Entered 2026-10-04; all entry conditions in `docs/strategy.md` §11
confirmed by the user.

## Next task

**M31 gate run 2026-10-04: BLOCK** (`docs/gates/M31/summary.md`). Floors VETO (`floors.md`): R-015 floor-1 fixes, floor-1 sweep gap, F2 leak via global `StudyAIOError` handler (concepts site) + R-012, 4 R-007 rulings, R-004. Functional: DEVOPS-005 pipeline red-proof needs an authorised throwaway push. `kit/retrofit` @ `2da6f17` is pushed; pipeline #523 green.

**Proposed next wave (awaiting user go-ahead):** `backend` fixes the R-015 floor-1 leaks + R-016 functional bugs; `ai` fixes classify known-courses leak + quick-capture `txt`; `safety` closes its floor-1 sweep gap for join-scoped tables and re-reviews.

**Integration branch.** `kit/retrofit` @ `9b3ef84` = … → QA-011 (`c04b31d`) → DEVOPS-005bc (`9b3ef84`); before that `02c9443` = ARCH-001 → DEVOPS-002 → QA-004 → DEVOPS-005a → ARCH-006 (`da8c596`) → SAFETY-003 (bc55b24) → BACKEND-008 → SAFETY-009 → BACKEND-010 (`718faa0`) → QA-007 (14 cherry-picks). Local only, not pushed.

**User rulings 2026-10-04** (`docs/decisions.md` § Rulings): re-summarize + regeneration + leaderboard → fix code (next wave: `data`/`ai`/`backend`/`frontend`); single-item deletes → amend floor 4 (ADR 0004); embeddings → in floor 3. Throwaway red-proof push authorised.

## Active

| Task | Owner | Dispatched | Worktree |
|---|---|---|---|
| M31-S2-SAFETY-012 (floor-1 sweep gap; F2 pins: concepts site, worker, global handler) | `safety` | 2026-10-04 | isolated |
| M31-S2-BACKEND-013 (R-015 × 6 backend sites; `studyaio_error_handler` stops echoing `AgentError`) | `backend` | 2026-10-04 | isolated |
| M31-S2-AI-014 (redact at `AgentError` construction / R-012; `_get_known_courses` scope; quick-capture `txt`) | `ai` | 2026-10-04 | isolated |
| M31-S2-ARCH-015 (ADR 0004 floor-4 item deletes; floor 3 covers embeddings) | `architect` | 2026-10-04 | isolated |
| M31-S2-DATA-017 (summary version retention; soft-retire flashcards/quiz questions; leaderboard opt-in) | `data` | 2026-10-04 | isolated |

## Completed

_Rows for the milestone just closed are moved to `docs/plan/archive/<id>.md`
at its gate, leaving one pointer line here. This file is read **in full** at the start of every session
(`load_order`), so an unarchived plan is a cost paid on every prompt for work that finished months ago._

Keep the current milestone's tasks here; roll earlier milestones into `docs/plan/archive/<milestone>.md` at the gate.

| Task | Owner | Branch | Evidence | Completed |
|---|---|---|---|---|
| M31-S1-ARCH-001 | `architect` | `task/M31-S1-ARCH-001-adapter-contract` @ `0e96c9a` (not merged) | `pytest tests/contracts -q` → `16 passed in 1.15s` (re-run by Orchestrator); ruff check/format clean | 2026-10-04 |
| M31-S1-DEVOPS-002 | `devops` | `task/M31-S1-DEVOPS-002-clean-clone-test` @ `7cd283c` (stacked on ARCH-001; not merged) | `make test` from a venv-less worktree (bootstrap included) → `2608 passed, 151 warnings in 142.15s`, exit 0 (re-run by Orchestrator); devops clean-clone run `2607 passed, 1 skipped`; empty collection exits 5 → make error | 2026-10-04 |
| M31-S1-QA-004 | `qa` | `task/M31-S1-QA-004-coverage-thresholds` @ `18b931d` (stacked; not merged) | Orchestrator re-run: `pytest tests/unit --cov=app` → `Required test coverage of 75.0% reached. Total coverage: 85.81%`, `2277 passed`; subset with `--cov` → `FAIL Required test coverage of 75.0% not reached` exit 1. **Conditional:** "a drop fails `make test`" closes with M31-S1-DEVOPS-005a (Makefile is devops-owned) | 2026-10-04 |
| M31-S1-ARCH-006 (ADR 0003, floor 3 amended; added on user agreement) | `architect` | `task/M31-S1-ARCH-006-floor3-adr` @ `4a21c09` (off `7cd283c`, isolated worktree; not yet cherry-picked onto the stack) | Orchestrator: `grep get_agent(` outside agents/pipeline → exactly the 5 ADR sites; `pytest tests/contracts` on the branch → `15 passed, 1 skipped` (skip = strategy.md absent there); agent `make test` → `2607 passed, 1 skipped` | 2026-10-04 |
| M31-S1-DEVOPS-005a (unit tier) | `devops` | `task/M31-S1-DEVOPS-005a-coverage-gates` @ `7393953` | Agent: `make test` → `Required test coverage of 75.0% reached. Total coverage: 85.81%`, `2610 passed`. Orchestrator: `make test TEST_PATHS=tests/unit/test_smoke.py COV_ARGS="--cov=app"` → `FAIL Required test coverage of 75.0% not reached` / `make: *** Error 1`; `glab ci lint` → valid. Closes QA-004's condition. **Not done:** integration tier (measures 43.52% vs 70, blocked on user); pipeline proof (needs a push, awaiting user) | 2026-10-04 |
| M31-S1-SAFETY-003 | `safety` | `task/M31-S1-SAFETY-003-floor-tier` @ `7c3df48` (off `4a21c09`; not yet on `kit/retrofit`) | Orchestrator re-run: `pytest tests/safety -q` → `4 failed, 23 passed, 4 xfailed` — red **by design** (`test(red):`), each red = a live violation, verified in code. Every floor maps to named tests (`tests/safety/FLOORS.md`), each shown red on an injected violation. ADR 0003: **APPROVE**. M31 gate: **VETO** | 2026-10-04 |
| M31-S1-BACKEND-008 | `backend` | `task/M31-S1-BACKEND-008-floor-fixes` @ `7eecbac` (da8c596 → bc55b24 [=7c3df48] → a2cd687 → b5f57e6 → 7eecbac; isolated worktree) | Orchestrator re-run: `pytest tests/safety -q` → `2 failed, 25 passed, 4 xfailed` (the 4 target reds green; the 2 left are stale inventory entries only `safety` may prune); `test_floor_fixes.py` → `7 passed`. Agent `make test` → `2616 passed, 1 skipped`, 85.87%. Diff checked by hand: only `backend` paths + unowned unit test. **Conditional:** safety review (SAFETY-009) | 2026-10-04 |
| M31-S1-SAFETY-009 (review of BACKEND-008) | `safety` | `task/M31-S1-SAFETY-009-review-floor-fixes` @ `65adbfc` (7eecbac → 8654c6b → 65adbfc) | Orchestrator re-run: `pytest tests/safety -q` → `3 failed, 30 passed, 4 xfailed`; the 3 = new `test(red)` provider-error echo at qa/chat (verified in code: `api/qa.py:94-95`, `chat_service.py:222,357`). V1, V2, V3/V4 **APPROVE** (regression pins rewritten to discriminate, mutation-checked); R-008 approved for test-ai only. Inventories pruned. VETO stands | 2026-10-04 |
| M31-S1-BACKEND-010 | `backend` | `task/M31-S1-BACKEND-010-redact-provider-errors` @ `718faa0` (65adbfc → 3f11acf → 718faa0; isolated) | Orchestrator re-run: `pytest tests/safety -q` → `33 passed, 4 xfailed` (**floor tier green**, 0 failed, no XPASS); redaction unit tests `11 passed`. Agent full suite `2620 passed, 1 skipped`, 85.92%. Diff checked by hand: `backend` paths + unowned unit test only. Touches floor 2 → `safety` confirms at gate | 2026-10-04 |
| M31-S1-QA-007 | `qa` | `task/M31-S1-QA-007-integration-coverage` (89dfc8e..50f5c71, 14 commits; cherry-picked onto `kit/retrofit`) | Orchestrator re-run on the task branch: `scripts/test-integration.sh --cov=app --cov-fail-under=70` → `Required test coverage of 70% reached. Total coverage: 73.18%`, `508 passed, 20 xfailed`, exit 0 (baseline 43.52%, 121 passed). Scope checked: only `tests/integration/**`. 20 strict xfails = real bugs → R-015..R-017 | 2026-10-04 |
| M31-S1-DEVOPS-005b + 005c (+ R-014) | `devops` | `task/M31-S1-DEVOPS-005bc-floor-integration-gates` @ `ea2f64a` (off `02c9443`; cherry-picked onto `kit/retrofit` as `9b3ef84`) | Orchestrator: diff = Makefile, `.gitlab-ci.yml`, `scripts/{test-integration.sh,coverage-tier.py}`, `.gitignore`; `coverage-tier.py` → 75/70/95, unknown tier rc=1; `glab ci lint` valid; floor gate → `Required test coverage of 95% reached. Total coverage: 96.55%`, `33 passed, 4 xfailed`. Agent: drop demos red for floor (99 → fail) and integration (99 → fail); integration gate 73.00% with the stale XPASS deselected; `make test` = unit 85.92% + floor 96.55%. **Pipeline proof outstanding** (push not yet authorised) | 2026-10-04 |
| M31-S1-QA-011 | `qa` | `task/M31-S1-QA-011-xfail-cleanup` @ `c04b31d` (fast-forwarded into `kit/retrofit`) | Scope: `pyproject.toml` (coverage concurrency) + 3 integration test files. Agent: integration `Total coverage: 87.65%`, `510 passed, 18 xfailed`, exit 0; `make test` 85.92%, `2621 passed`; floor `33 passed, 4 xfailed`; xdist coverage identical to serial. Stale V1 xfail removed; test-ai xfail was a wrong test (never stored a key) — rewritten, proven both ways; daily-reminder xfail re-seeded so it fails on the real bug. Orchestrator full-gate run on `kit/retrofit` @ `9b3ef84`: `make test` → unit `75.0% reached. Total coverage: 85.92%`, `2621 passed`; floor `95% reached. Total coverage: 96.55%`, `33 passed, 4 xfailed` (exit 0); `make test-integration` → `70% reached. Total coverage: 86.98%`, `510 passed, 18 xfailed` (exit 0) | 2026-10-04 |
| M31-S2-DEVOPS-016 (DEVOPS-005 pipeline red-proof; contracts in CI; runbook) | `devops` | worktree `2bf30fe`/`27b096c`/`3695fa4` → cherry-picked onto `kit/retrofit` as `cbd7d72`/`d338dc2`/`e6ed963` | Orchestrator, jobs read by name via `glab api`: **#526** `test-floor` **failed** (job 4307, `AssertionError: Floor 2: credential committed to the tree: docs/redproof/sentinel.txt:1 AWS access key id`); **#527** `backend-tests` **failed** (job 4312, `FAIL Required test coverage of 75.0% not reached. Total coverage: 61.42%`). #525 `test-floor` false-green (job 4301): no git in image → scan fell back to `services/app` only; fixed by `cbd7d72`, loud-fallback routed to SAFETY-012 (R-018). `glab ci lint` valid. **Open:** 3 throwaway remote branches not deleted (hook blocks agents) — user to delete | 2026-10-04 |

## Blocked

| Task | Owner | Blocked on | Since |
|---|---|---|---|

## Open gates

| Gate | Verdict | Summary | Date |
|---|---|---|---|
| M31 | **BLOCK** — `safety` VETO + DEVOPS-005 pipeline red-proof missing | [`docs/gates/M31/summary.md`](../gates/M31/summary.md) · floors: [`floors.md`](../gates/M31/floors.md) | 2026-10-04 |

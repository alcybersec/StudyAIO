# M31 — Maintenance · Gate summary

**Date** 2026-10-04 · **Branch** `kit/retrofit` @ `2da6f17` (30 commits ahead of `origin/main`, 0 behind)
· **Pipeline** GitLab #523 on `2da6f17` · **Kit** 1.10.3

**Verdict: BLOCK** — Floors is VETO (not overridable), and Functional misses on M31-S1-DEVOPS-005.

---

## Functional

Every M31 task in `docs/strategy.md` §11 against its acceptance criterion. Evidence is the handoff
line recorded in `docs/plan/README.md` § Completed, re-run by the Orchestrator where noted.

| Task | Acceptance | Evidence | Met? |
|---|---|---|---|
| M31-S1-ARCH-001 | Every `CONTRACTS.md` entry names consumers; boundaries match §2. User acceptance of boundaries is a gate question | `pytest tests/contracts -q` → `16 passed` (Orchestrator re-run). ADR 0002 (module boundaries) is still **Proposed** | Met for the task; **user acceptance of ADR 0002 outstanding** (gate question, see Verdict) |
| M31-S1-DEVOPS-002 | Clean clone → green in one documented command; exit 5 fails | `make test` from venv-less worktree → `2608 passed`, exit 0 (Orchestrator re-run); empty collection → make error | Met |
| M31-S1-SAFETY-003 | Each floor has ≥1 test that fails when violated | `tests/safety/FLOORS.md` maps floors 1–4 to named tests, each shown red on an injected violation; `safety` re-confirms in `floors.md` | Met |
| M31-S1-QA-004 | Deliberate coverage drop fails `make test` locally and, once DEVOPS-005 lands, in the pipeline | Local: subset run → `FAIL Required test coverage of 75.0% not reached`, exit 1 (Orchestrator re-run). Pipeline half: see DEVOPS-005 | Local met; pipeline half **not met** |
| M31-S1-DEVOPS-005 (005a/b/c) | Floor tier + thresholds wired into `.gitlab-ci.yml`; **a deliberate floor violation and a deliberate coverage drop each redden the pipeline** | Jobs exist and enforce: #523 `test-floor` 95 → 96.55%, `integration-tests` 70 → 87.65%, `backend-tests` 75 → 85.92% (qa, by job name). Local drop demos red for floor and integration. **No pipeline has ever been shown red** on a deliberate violation (qa: 20 pipelines listed, all success) | **MISS → BLOCK** |
| M31-S1-ARCH-006 | Floor 3 reworded with exact request-time allowlist; user agreement recorded | ADR 0003 Accepted; `grep get_agent(` outside agents/pipeline → exactly the 5 ADR sites; §6 floor 3 annotated with user agreement | Met |
| M31-S1-QA-007 | Integration coverage ≥ 70% against real Postgres + Redis; tests assert behaviour | `scripts/test-integration.sh --cov=app --cov-fail-under=70` → 73.18%, now 87.65% after QA-011's greenlet fix; 18 strict xfails pin real bugs (R-015, R-016) | Met |
| M31-S1-BACKEND-008 | `pytest tests/safety` → 0 failed (strict xfails remain until the user rules) | Orchestrator re-run → 4 target reds green; `safety` APPROVE in SAFETY-009 | Met |
| M31-S1-SAFETY-009 | Each fix APPROVE or a red test naming the hole | V1–V4 APPROVE; new red test for qa/chat echo → BACKEND-010 | Met |
| M31-S1-BACKEND-010 | `pytest tests/safety` → 0 failed | Orchestrator re-run → `33 passed, 4 xfailed`; `safety` confirms at gate, mutation-checked (`floors.md`) | Met |
| M31-S1-QA-011 (cleanup, not in §11 table) | — | Integration `510 passed, 18 xfailed`, 87.65% | n/a |

## Tests

Dispatched to `qa` (review mode, no files edited). Commands and last lines as returned:

```
$ make test                       # unit + golden + contracts, then floor
Required test coverage of 75.0% reached. Total coverage: 86.68%
2621 passed, 151 warnings in 288.65s
Required test coverage of 95% reached. Total coverage: 96.55%
33 passed, 4 xfailed, 6 warnings in 62.88s                      (exit 0)

$ make test-integration
Required test coverage of 70% reached. Total coverage: 87.65%
510 passed, 18 xfailed, 12 warnings in 155.10s                  (exit 0)
```

| Tier | Threshold | Local | Pipeline #523 |
|---|---|---|---|
| unit | 75 | 86.68% | `backend-tests` success, 85.92%, "Required … 75.0% reached" (`-n auto -x`) |
| integration | 70 | 87.65% | `integration-tests` success, 87.65%, fail-under 70 via `coverage-tier.py` |
| floor | 95 | 96.55% | `test-floor` success, 96.55%, fail-under 95 via `coverage-tier.py` |

Pipeline #523 by job name: `backend-tests` success · `test-floor` success · `integration-tests`
success · `e2e-tests` success · `frontend-checks` success · `python-lint` success. No job `skipped`.

Gaps — none of these is a pass:

- **Pipeline red-proof absent.** No deliberate violation has reddened a pipeline (Functional miss above).
- **`tests/contracts` does not run in CI.** `Makefile:75` includes it; `.gitlab-ci.yml` has no
  reference (Orchestrator `grep`). `backend-tests` 2288 + golden 317 = 2605 vs 2621 locally.
- **10 Playwright tests skipped** in `e2e-tests` via conditional `test.skip()` (auth, admin,
  course-management specs).
- **22 strict xfails, 0 XPASS:** floor 4 (R-007 rulings), integration 18 (R-015 floor-1 × 8,
  R-016 functional × 8, floor-4 duplicate × 1, quick-capture `txt` × 1). Known bugs, not passes.

Snapshots: none exist (no `__snapshots__`, no Playwright snapshot dirs); golden tier is 18
structural files, unchanged this milestone.

`qa` recommendation: CONDITIONAL.

## Floors

**`safety` verdict: VETO** — see [`floors.md`](floors.md). Written by `safety`; the Orchestrator
does not edit or summarise it.

## Operational

- **Scope of change vs `origin/main`:** 7 app files (`api/{courseops,qa,settings}.py`,
  `services/{account,chat,courseops,settings}_service.py`), CI, Makefile, scripts, tests, docs.
  No new pipeline stage, endpoint or feature.
- **Metrics/logs:** no new stage, so no new counters required. Changed error paths keep structured
  logs with redacted text (`qa_embedding_error`, `qa_agent_error`, `test_ai_failed`, chat
  send/stream). Not new: `main.py:519` `unhandled_studyaio_error` logs and returns `str(exc)` —
  the F2 leak `safety` found at the concepts site.
- **Data model:** unchanged (no migration, no model file vs `origin/main`). Backup coverage
  unaffected.
- **Rollback:** `kit/retrofit` is not merged to `main`; prod runs `main` images. Rollback = do
  not merge / revert the merge commit. No schema to roll back.
- **Runbook:** `docs/developer_guide.md` documents `make bootstrap` and `make test-integration`;
  it does **not** document `make test-floor` or the coverage tiers and `scripts/coverage-tier.py`.
  Gap — owner `devops`.

## Milestone additions

§11: "the floor tier must be non-empty and green, and every floor in §6 must map to a named test."

- Non-empty and green: `33 passed, 4 xfailed`, 96.55% locally and in `test-floor` #523. **Met.**
- Every floor maps to a named test: `tests/safety/FLOORS.md`, confirmed per floor in `floors.md`. **Met.**

The addition is met; it does not by itself make the floors hold — see Floors.

## Verdict

**BLOCK.**

Blocking dimensions:

1. **Floors — VETO** (`safety`, not overridable). Lift conditions are in `floors.md`; in short:
   R-015 floor-1 fixes (`backend`, `ai`); floor-1 sweep extended to bodies, typed path params and
   functions (`safety`); F2 leak via the global `StudyAIOError` handler at the concepts site plus
   worker-side R-012 (`ai`, `backend`, `safety`); the 4 R-007 rulings (**user**); R-004 embeddings
   scope (**user** + `safety`).
2. **Functional — M31-S1-DEVOPS-005 miss.** A deliberate floor violation and a deliberate coverage
   drop must each be shown reddening a GitLab pipeline (throwaway branch push; **user** to
   authorise the push, then `devops`).

Non-blocking items to schedule (owner → proposed task ID, to be numbered when dispatched):

| Item | Owner | Task |
|---|---|---|
| Run `tests/contracts` in CI | `devops` | M31-S2-DEVOPS-0xx |
| Document `make test-floor`, tiers and `coverage-tier.py` in the developer guide | `devops` | same task |
| Triage 10 conditional e2e skips | `qa` | M31-S2-QA-0xx |
| R-016 functional bugs (account deletion FK, MFA disable, billing free tier, reminders, achievement notif, gcal, quick-capture `txt`) | `backend`, `ai` | M31-S2-BACKEND/AI-0xx |
| User accepts ADR 0002 (module boundaries, Proposed) — ARCH-001's gate question | user → `architect` | — |

**Carried conditions:** this is the first gate under the kit. No condition has survived two
milestones.

Signers:

- Orchestrator — BLOCK, 2026-10-04
- `safety` — VETO (`floors.md`)
- `architect` — not required: no contract changed in this review (ADR 0003 was accepted inside the milestone)

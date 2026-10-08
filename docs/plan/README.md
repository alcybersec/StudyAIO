# Dispatch State

**Owner.** Orchestrator. **Updated.** After every task completion and every gate.

Source of truth for "what is next". Subagents never edit this file; they emit handoff notes and the
Orchestrator updates here.

---

## Current milestone

**M32 — Next feature.** Opened 2026-10-08 on the user's acceptance of the M31 gate re-run
(CONDITIONAL). The feature itself is not yet scoped — the user names it; the Orchestrator expands
§11 tasks then. Until then, M32-S1 carries the M31 conditions.

## Next task

Wave 1 dispatched 2026-10-08 (see Active). **Queued:** M32-S1-BACKEND-006 (C6) after BACKEND-002 lands (overlapping services). C1 (ADR 0002) waits on the user's review.

**Integration branch.** `kit/retrofit` @ `2f3296d`+ (code `8d9de14`, pipeline #537 green) — pushed,
not merged to `main`; no MR opened.

## Active

| Task | Owner | Dispatched | Worktree |
|---|---|---|---|
| M32-S1-BACKEND-001 + 005 (C2a account-deletion FK; C5/R-020 purge covers deleted courses' summary blobs) | `backend` | 2026-10-08 | isolated |
| M32-S1-BACKEND-002 (C2b billing free tier, MFA disable, achievement `title`, gcal `timeMin`) | `backend` | 2026-10-08 | isolated |
| M32-S1-SAFETY-004 (C4 handler pin; F-2; red pins for C5 and C6) | `safety` | 2026-10-08 | isolated |

## Completed

_Rows for the milestone just closed are moved to `docs/plan/archive/<id>.md`
at its gate, leaving one pointer line here._

- M31 — Maintenance: [`archive/M31.md`](archive/M31.md) (closed 2026-10-08, CONDITIONAL, C1–C6 → M32)

| Task | Owner | Branch | Evidence | Completed |
|---|---|---|---|---|
| M32-S1-QA-003 (C3: e2e 0 skipped) | `qa` | `fc6dbb7` → `kit/retrofit` (see log) | Diff = `services/ui/e2e/**` only (specs, `fixtures.ts`, new `seed_e2e.py` DB seed via app models — no public API creates course/concept/admin in CI's self-hosted, worker-less mode). Agent, local CI-mirror stack: `CI=1 npx playwright test` → `64 passed (2.9m)`, 0 skipped (was 54 passed / 10 skipped). Two specs had never run (reserved `@test.local` email, stale copy). **Pipeline confirmation pending next push.** Risk: a11y colour-contrast flake on offline toast | 2026-10-08 |
| M32-S1-ARCH-008 (ADR 0004 #1 purge wording corrected; ADR 0003 header) | `architect` | `128abec` → `kit/retrofit` `948353a` | Diff = 2 ADRs. `pytest tests/contracts` → `25 passed`. ADR 0004 § Correction 2026-10-08 has a placeholder for BACKEND-005's final purge mechanism (Orchestrator fills) | 2026-10-08 |

## Blocked

| Task | Owner | Blocked on | Since |
|---|---|---|---|
| M32-S1-ARCH-007 (C1: ADR 0002 module boundaries) | `architect` | user review of `docs/adr/0002-module-boundaries.md` | 2026-10-08 |

## Open gates

| Gate | Verdict | Summary | Date |
|---|---|---|---|

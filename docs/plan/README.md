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
| M32-S1-BACKEND-006 (C6: `user_id` required + unconditional filter in services) | `backend` | 2026-10-08 | isolated |

## Completed

_Rows for the milestone just closed are moved to `docs/plan/archive/<id>.md`
at its gate, leaving one pointer line here._

- M31 — Maintenance: [`archive/M31.md`](archive/M31.md) (closed 2026-10-08, CONDITIONAL, C1–C6 → M32)

| Task | Owner | Branch | Evidence | Completed |
|---|---|---|---|---|
| M32-S1-AI-012 (C6 pipeline: `_get_or_create_course` owner required; artifact row owner wins, mismatch logged) | `ai` | `03c2ff9`/`68092b8`/`a59fd27` → `kit/retrofit` head `f72a928` | Diff = 7 pipeline files + 1 unit test. **Orchestrator red-check** (agent not red-first): pre-fix pipeline → `5 failed, 1 passed`; fixed → pipeline unit `75 passed`. Floor `2 failed, 78 passed` — both BACKEND-006's (services/ C6 entries; ledger segment) | 2026-10-08 |
| M32-S1-SAFETY-009 (review BACKEND-001/005; classify pipeline under C6) | `safety` | `dc749bd`/`7aebc43` → `kit/retrofit` head `a8dc819` | Diff = `tests/safety/**`. Agent floor: `2 failed, 78 passed`, 97.53% — both intended: C6 pin (services/ + `classify._get_or_create_course`) and new floor-4 pin (purge must skip empty/non-id ledger segment — an S3 folder placeholder would sweep all of `summaries/`). BACKEND-001/005 otherwise APPROVE (mutation-checked; added cross-user ledger pin). 10/11 pipeline stages classified. Fixes routed: ledger segment + S3 list failure → BACKEND-006; `_get_or_create_course` + row-owner-wins → AI-012 | 2026-10-08 |
| M32-S1-QA-010 (retire 6 R-016 xfails) | `qa` | `f8624c8` → `kit/retrofit` (see log) | Diff = 32 pure deletions, 5 integration files. Agent: fixes reverted → exactly those `6 failed`; restored → `529 passed`, 0 xfailed, coverage gate exit 0. **Integration tier now has 0 xfails (C2 met)** | 2026-10-08 |
| M32-S1-ARCH-011 (ADR 0004 § Correction: ledger purge mechanism, placeholder filled) | `architect` | `128b37d` → `kit/retrofit` (see log) | Diff = ADR 0004 only; checked against `a3ab6ce`. `pytest tests/contracts` → `25 passed`. Wording under SAFETY-009 review | 2026-10-08 |
| M32-S1-SAFETY-004 (C4 handler pin direct; F-2; red pins for C5, C6) | `safety` | `131fb96`/`b8294f6`/`418cc46` → `kit/retrofit` head `d424aa2` | Diff = `tests/safety/**`. Agent: floor `2 failed, 75 passed`, 97.46% — the 2 = C5 and C6 pins. Handler pin kills 3 mutants incl. the M31 survivor. **C6 pin flags 71 functions, not 5** → user ruled scope (decisions.md) | 2026-10-08 |
| M32-S1-BACKEND-002 (C2b: billing free limits, MFA-disable 400, achievement `title`, gcal RFC 3339) | `backend` | `b34c2c5`..`55ed110` → `kit/retrofit` head `94dbf00` | Diff = 4 app files + 3 unit tests (two old mocks had hidden bugs 1 and 3). **Orchestrator red-check** (agent not test-first): pre-fix → `6 failed`; fixed → `26 passed`. Agent integration: 4 strict XPASS → QA-010 | 2026-10-08 |
| M32-S1-BACKEND-001 + 005 (C2a FK-safe account deletion; C5 deleted-course ledger purge) | `backend` | `624eade`/`b1c712c` → `kit/retrofit` `b3b1bea`/`a3ab6ce` | Agent: unit services+core `1066 passed`; integration `2 failed, 523 passed` = 2 strict XPASS → QA-010. **Orchestrator: scratch worktree kit/retrofit + these → floor `1 failed, 76 passed`** (C5 pin green; only C6 left). Design = ledger (user kept it over per-user prefix; decisions.md) → ARCH-011, SAFETY-009 | 2026-10-08 |
| M32-S1-QA-003 (C3: e2e 0 skipped) | `qa` | `fc6dbb7` → `kit/retrofit` (see log) | Diff = `services/ui/e2e/**` only (specs, `fixtures.ts`, new `seed_e2e.py` DB seed via app models — no public API creates course/concept/admin in CI's self-hosted, worker-less mode). Agent, local CI-mirror stack: `CI=1 npx playwright test` → `64 passed (2.9m)`, 0 skipped (was 54 passed / 10 skipped). Two specs had never run (reserved `@test.local` email, stale copy). **Pipeline confirmation pending next push.** Risk: a11y colour-contrast flake on offline toast | 2026-10-08 |
| M32-S1-ARCH-008 (ADR 0004 #1 purge wording corrected; ADR 0003 header) | `architect` | `128abec` → `kit/retrofit` `948353a` | Diff = 2 ADRs. `pytest tests/contracts` → `25 passed`. ADR 0004 § Correction 2026-10-08 has a placeholder for BACKEND-005's final purge mechanism (Orchestrator fills) | 2026-10-08 |

## Blocked

| Task | Owner | Blocked on | Since |
|---|---|---|---|
| M32-S1-ARCH-007 (C1: ADR 0002 module boundaries) | `architect` | user review of `docs/adr/0002-module-boundaries.md` | 2026-10-08 |

## Open gates

| Gate | Verdict | Summary | Date |
|---|---|---|---|

# Dispatch State

**Owner.** Orchestrator. **Updated.** After every task completion and every gate.

Source of truth for "what is next". Subagents never edit this file; they emit handoff notes and the
Orchestrator updates here.

---

## Current milestone

**M33 — Trust and retention** (opened 2026-10-11 on the user's acceptance of the M32 gate, CONDITIONAL). Source:
`docs/audits/2026-10-10-product-audit.md`; outline in `docs/strategy.md` §11. M32 is archived in
[`archive/M32.md`](archive/M32.md).

## Next task

**M33-S1** (strategic bet: weak-spot engine, user 2026-10-11). Unblocked now: M33-S1-OPS-004 (G4, after the next
02:00 UTC backup), M33-S1-AI-012 (eval set in CI), M33-S1-AI-014 (relevance floor), M33-S1-BACKEND-015/016/017
(feedback, usage events, consent). M33-S1-AI-013 after AI-012 (needs the baseline). M33-S2 starts with
M33-S2-ARCH-018 (ADR 0007), which needs the user's acceptance before S2 implementation.

**M33 GitLab issues (2026-10-11):** GL#32–#51 = M33-S1-OPS-004 … M33-S3-DEVOPS-030 in §11 order (label `M33`).

## Active

| Task | Owner | Dispatched | Worktree |
|---|---|---|---|
| M33-S1-DATA-031 (schema: `ai_feedback`, `usage_events`, consent fields — for GL#36/#37/#38) | `data` | 2026-10-11 | isolated |
| M33-S1-AI-012 (GL#33: ≥20 eval cases, offline CI check, baseline) | `ai` | 2026-10-11 | isolated |
| M33-S1-AI-014 (GL#35: relevance floor + follow-up retrieval; retrieval half by `backend`) | `backend` | 2026-10-11 | isolated |

**GL#31 (2026-10-10):** chat follow-ups lose course/week scope (prod repro; a course's week 3 has 8 indexed chunks) — pulled into M32 wave 1 as M32-S4-BACKEND-023 (audit AI-06 overlap).

**M32 GitLab issues (2026-10-10):** GL#11–#30 = M32-S4-BACKEND-001 … M32-S4-QA-020 in §11 order (labels `M32`, `audit-2026-10`). Queued: AI-007 (AI-03, after wave 1), BACKEND-009 (QUOTA-01/COST-01; PROD-08 decided: beta users get Pro).

## Completed

_Rows for the milestone just closed are moved to `docs/plan/archive/<id>.md`
at its gate, leaving one pointer line here._

- M31 — Maintenance: [`archive/M31.md`](archive/M31.md) (closed 2026-10-08, CONDITIONAL, C1–C6 → M32)
- M32 — Safe to grow: [`archive/M32.md`](archive/M32.md) (closed 2026-10-11, CONDITIONAL accepted; 71 rows; G4 → M33)

| Task | Owner | Branch | Evidence | Completed |
|---|---|---|---|---|

## Blocked

| Task | Owner | Blocked on | Since |
|---|---|---|---|

## Open gates

| Gate | Verdict | Summary | Date |
|---|---|---|---|
| M32 | **CONDITIONAL — accepted by the user 2026-10-11**; G1–G3 closed, G4 → M33-S1-OPS-004 | [`summary.md`](../gates/M32/summary.md) · floors: [`floors.md`](../gates/M32/floors.md) | 2026-10-11 |

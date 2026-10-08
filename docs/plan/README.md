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

**M32-S1-BACKEND-001** — R-016 account-deletion FK (condition C2, first: it blocks floor 4's
sanctioned erasure path). Then the rest of C2–C6 in `docs/strategy.md` §11 M32. C1 (ADR 0002) waits
on the user's review.

**Integration branch.** `kit/retrofit` @ `2f3296d`+ (code `8d9de14`, pipeline #537 green) — pushed,
not merged to `main`; no MR opened.

## Active

| Task | Owner | Dispatched | Worktree |
|---|---|---|---|

## Completed

_Rows for the milestone just closed are moved to `docs/plan/archive/<id>.md`
at its gate, leaving one pointer line here._

- M31 — Maintenance: [`archive/M31.md`](archive/M31.md) (closed 2026-10-08, CONDITIONAL, C1–C6 → M32)

| Task | Owner | Branch | Evidence | Completed |
|---|---|---|---|---|

## Blocked

| Task | Owner | Blocked on | Since |
|---|---|---|---|
| M32-S1-ARCH-007 (C1: ADR 0002 module boundaries) | `architect` | user review of `docs/adr/0002-module-boundaries.md` | 2026-10-08 |

## Open gates

| Gate | Verdict | Summary | Date |
|---|---|---|---|

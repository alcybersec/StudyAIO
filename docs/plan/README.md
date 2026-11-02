# Dispatch State

**Owner.** Orchestrator. **Updated.** After every task completion and every gate.

Source of truth for "what is next". Subagents never edit this file; they emit handoff notes and the
Orchestrator updates here.

---

## Current milestone

**M35 — Delivery-chain hardening** (scope confirmed by the user 2026-11-02: the whole DevSecOps 90-day plan; Week 1 closes every S1). Scope in `docs/strategy.md` §11. M34 is archived in [`archive/M34.md`](archive/M34.md).

## Next task

**M34 closed 2026-10-22** (CONDITIONAL accepted; C1 D30 readout and C2 first prod targeted generation → M35, both carried twice; C3 dependency advisories fixed via MR !46). **Next: M35-W1-01** (registry token and deploy key scoped to environments), dispatched together with M35-W1-04 and the W1-10 tag protection (one sitting). Then W1-02, W1-03, W1-07, W1-09. R-010 decided (add the column): M35-R010-01 (`data`) runs in parallel with W1-01/W1-04, then R010-02, R010-03. Time-bound: M35-OPS-001 from 2026-11-14.

## Active

| Task | Owner | Dispatched | Worktree |
|---|---|---|---|
_none_

## Completed

_Rows for the milestone just closed are moved to `docs/plan/archive/<id>.md`
at its gate, leaving one pointer line here._

- M31 — Maintenance: [`archive/M31.md`](archive/M31.md) (closed 2026-10-08, CONDITIONAL, C1–C6 → M32)
- M32 — Safe to grow: [`archive/M32.md`](archive/M32.md) (closed 2026-10-11, CONDITIONAL accepted; 71 rows; G4 → M33)
- M33 — Trust and retention: [`archive/M33.md`](archive/M33.md) (closed 2026-10-15, CONDITIONAL accepted; 6 rows; C1–C4 → M34)
- M34 — Prove retention, close carried debt: [`archive/M34.md`](archive/M34.md) (closed 2026-10-22, CONDITIONAL accepted; 3 rows; C1–C2 → M35)

| Task | Owner | Branch | Evidence | Completed |
|---|---|---|---|---|


## Blocked

| Task | Owner | Blocked on | Since |
|---|---|---|---|

## Open gates

| Gate | Verdict | Summary | Date |
|---|---|---|---|
| M34 | **CONDITIONAL — accepted by the user 2026-10-22**; C1 D30 readout (≥ 2026-11-14), C2 first prod targeted generation, C3 pillow/certifi advisories fixed (MR !46). C1/C2 have survived two milestones. | [`summary.md`](../gates/M34/summary.md) · floors: [`floors.md`](../gates/M34/floors.md) (APPROVE) | 2026-10-22 |
| M33 | **CONDITIONAL — accepted by the user 2026-10-15**; C1 D7 readout (≥ 2026-10-22), C2 D30 readout (≥ 2026-11-14), C3 first non-root nightly backup (2026-10-16), C4 first prod targeted generation cites valid pages | [`summary.md`](../gates/M33/summary.md) · floors: [`floors.md`](../gates/M33/floors.md) (APPROVE) | 2026-10-15 |
| M32 | **CONDITIONAL — accepted by the user 2026-10-11**; G1–G4 all closed (G4: scheduled backup verified 2026-10-12) | [`summary.md`](../gates/M32/summary.md) · floors: [`floors.md`](../gates/M32/floors.md) | 2026-10-12 |

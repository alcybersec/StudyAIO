# Dispatch State

**Owner.** Orchestrator. **Updated.** After every task completion and every gate.

Source of truth for "what is next". Subagents never edit this file; they emit handoff notes and the
Orchestrator updates here.

---

## Current milestone

**M34 — Prove retention, close carried debt** (opened 2026-10-16; scope confirmed by the user: hardening and debt, no strategic bet). Tasks in `docs/strategy.md` §11. M33 is archived in [`archive/M33.md`](archive/M33.md).

## Next task

**M34 deployed 2026-10-18** — `main` @ `b637dd2` (MR !45; pipeline all 11 jobs green incl. `deploy-selfhosted`). Prod verified: all services on `b637dd2`, AI and maintenance pools run as uid 999 with writable data/HOME and a readable login copy, migrations at head `c3e5a7b9d1f2`, OAuth tokens all NULL, three Celery nodes answer, health ready, 0 errors; pre-deploy dump taken. Host prep: login dir and data/ owner uid 999 (groups unchanged), deploy.sh reinstalled (backup `deploy.sh.bak-20261018-m34`). Remaining M34: M34-OPS-002 D30 (from 2026-11-14), M34-OPS-004 first prod targeted generation (none yet as of 2026-10-22); then the M34 gate. M34-OPS-001 D7 done 2026-10-22.

## Active

| Task | Owner | Dispatched | Worktree |
|---|---|---|---|
| M34 e2e: fix `first-run.spec.ts` for the server-side checklist (CI red on `e2e-tests`, 130 passed); add onboarding, study-card feedback, Claude Code availability cases | `qa` | 2026-10-16 | isolated |

Held branches (not on trunk): `hold/m34-contract-red` (red contract tests for implementers), `hold/m34-sec006` (`b27fc19`), `hold/m34-floor2-pin` (`5fc2de4`, floor-2 secrets-at-rest pin, red until SEC-005), `hold/m34-contract-red` still carries the SEC-005 secrets-at-rest contract tests (the rest landed in `d2f276d`).

## Completed

_Rows for the milestone just closed are moved to `docs/plan/archive/<id>.md`
at its gate, leaving one pointer line here._

- M31 — Maintenance: [`archive/M31.md`](archive/M31.md) (closed 2026-10-08, CONDITIONAL, C1–C6 → M32)
- M32 — Safe to grow: [`archive/M32.md`](archive/M32.md) (closed 2026-10-11, CONDITIONAL accepted; 71 rows; G4 → M33)
- M33 — Trust and retention: [`archive/M33.md`](archive/M33.md) (closed 2026-10-15, CONDITIONAL accepted; 6 rows; C1–C4 → M34)

| Task | Owner | Branch | Evidence | Completed |
|---|---|---|---|---|
| M34-OPS-001 (M33 C1): D7 readout, users with a Study-tonight plan vs without | Orchestrator | — (prod query, counts only) | Window: day 1–7 after each user's first plan (no-plan users anchored on the 2026-10-15 launch). With plan: 1 user, 1 active in days 1–7, 1 active in the last 7 days. Without plan: 2 users, 0 and 0. Descriptive only (n=3; ADR 0007: no hold-out group) | 2026-10-22 |
| M34-OPS-003 (M33 C3): first nightly backup under the non-root maintenance pool | Orchestrator | — (prod check) | 2026-10-16 02:00 UTC run: db + data archives written, owned by uid 999; `run_backup` status ok in 23 s; `studyaio_backup_last_success_timestamp_seconds` advanced | 2026-10-16 |


## Blocked

| Task | Owner | Blocked on | Since |
|---|---|---|---|

## Open gates

| Gate | Verdict | Summary | Date |
|---|---|---|---|
| M33 | **CONDITIONAL — accepted by the user 2026-10-15**; C1 D7 readout (≥ 2026-10-22), C2 D30 readout (≥ 2026-11-14), C3 first non-root nightly backup (2026-10-16), C4 first prod targeted generation cites valid pages | [`summary.md`](../gates/M33/summary.md) · floors: [`floors.md`](../gates/M33/floors.md) (APPROVE) | 2026-10-15 |
| M32 | **CONDITIONAL — accepted by the user 2026-10-11**; G1–G4 all closed (G4: scheduled backup verified 2026-10-12) | [`summary.md`](../gates/M32/summary.md) · floors: [`floors.md`](../gates/M32/floors.md) | 2026-10-12 |

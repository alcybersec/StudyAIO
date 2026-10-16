# Dispatch State

**Owner.** Orchestrator. **Updated.** After every task completion and every gate.

Source of truth for "what is next". Subagents never edit this file; they emit handoff notes and the
Orchestrator updates here.

---

## Current milestone

**M34 — Prove retention, close carried debt** (opened 2026-10-16; scope confirmed by the user: hardening and debt, no strategic bet). Tasks in `docs/strategy.md` §11. M33 is archived in [`archive/M33.md`](archive/M33.md).

## Next task

Wave 1 in flight (below). Applied: contracts amended per safety C3–C7 (`ead3e41`) + held tests repointed (`1798333`); ADR 0005 amendment (`8c25495`); AI-010 index split end to end (`a59636c`…`a842b60`: backend embed/store split, safety re-pins incl. `aembed_texts` and a worker-only chunk-store pin, pipeline switch, `_Precomputed` removed) with SEC-009 backend bits (template-only email logs, typed admin feedback view, no question text in qa logs, no model text in parsing logs, `proof.py` removed); SEC-005/008 contract review APPROVE-WITH-CHANGES (`4bce153`; floor-2 red pin held on `hold/m34-floor2-pin`); SEC-009 N-1 (`seed_e2e.py` refuses without `STUDYAIO_E2E_SEED=1` set by its fixture, and on a non-local database host; CI host `postgres` allowed); contracts (`4371b29`, amended `a2accb0`: models.secrets-at-rest v1 incl. `users.mfa_secret`, models.stripe-webhook-events v1, api.ai_feedback stays v1, api.onboarding v1, core.login-throttle-metrics v1, api.study-items v2) with red tests held on `hold/m34-contract-red` (`5d542b1`, `1437546`) for the implementers; ADR 0003 refresh (`110f84b`); FRONTEND-011 (`1eb41a5`: Sentry chunk 482 → 87 KB by importing only the used functions; QuickCaptureModal test deterministic, 20/20 under load), SEC-007 devops part (`8c64d1c`: pip-audit pinned, deploy key check round-trips the key — host deploy.sh reinstall needed at next deploy). Then: SEC-005 + SEC-008 implementation (`data`, `backend`) against the architect's red contract tests; BACKEND-012; AI-010 ai half (drop `_Precomputed`); SEC-007 fastapi cap lift (`backend`); safety review. Time-bound: M34-OPS-001 D7 readout from 2026-10-22, M34-OPS-002 D30 from 2026-11-14, M34-OPS-004 on first prod targeted generation.

## Active

| Task | Owner | Dispatched | Worktree |
|---|---|---|---|
| R-046 / C6: `hide_parameters=True` on every engine (bound values out of error logs) | `backend` | 2026-10-16 | isolated |
| M34-S2-SEC-008 (Stripe dedupe + ordering in Postgres) + M34-S3-BACKEND-012 (case-insensitive lookup, throttle counter, onboarding API) on held contract tests + data `524c5f2` | `backend` | 2026-10-16 | isolated |
| AI-010: ADR 0005 allowlist amended to the split functions | `architect` | 2026-10-16 | isolated |
| SEC-006 option F: safety §5 pins + repair of 27 floor-2 spawn tests the guard turned red (code held on `hold/m34-sec006`: `0307015`, `d68aeb8`) | `safety` | 2026-10-16 | isolated |

Held branches (not on trunk): `hold/m34-contract-red` (red contract tests for implementers), `hold/m34-sec006` (`b27fc19`), `hold/m34-floor2-pin` (`5fc2de4`, floor-2 secrets-at-rest pin, red until SEC-005), `hold/m34-data-stripe-onboarding` (`524c5f2`: `stripe_webhook_events` model, `users.onboarding_checklist`, migration `a1c2d3e4f5a6`, single head; lands with backend SEC-008/BACKEND-012 and safety's Stripe/UNOWNED_TABLES pins).

## Completed

_Rows for the milestone just closed are moved to `docs/plan/archive/<id>.md`
at its gate, leaving one pointer line here._

- M31 — Maintenance: [`archive/M31.md`](archive/M31.md) (closed 2026-10-08, CONDITIONAL, C1–C6 → M32)
- M32 — Safe to grow: [`archive/M32.md`](archive/M32.md) (closed 2026-10-11, CONDITIONAL accepted; 71 rows; G4 → M33)
- M33 — Trust and retention: [`archive/M33.md`](archive/M33.md) (closed 2026-10-15, CONDITIONAL accepted; 6 rows; C1–C4 → M34)

| Task | Owner | Branch | Evidence | Completed |
|---|---|---|---|---|
| M34-OPS-003 (M33 C3): first nightly backup under the non-root maintenance pool | Orchestrator | — (prod check) | 2026-10-16 02:00 UTC run: db + data archives written, owned by uid 999; `run_backup` status ok in 23 s; `studyaio_backup_last_success_timestamp_seconds` advanced | 2026-10-16 |


## Blocked

| Task | Owner | Blocked on | Since |
|---|---|---|---|

## Open gates

| Gate | Verdict | Summary | Date |
|---|---|---|---|
| M33 | **CONDITIONAL — accepted by the user 2026-10-15**; C1 D7 readout (≥ 2026-10-22), C2 D30 readout (≥ 2026-11-14), C3 first non-root nightly backup (2026-10-16), C4 first prod targeted generation cites valid pages | [`summary.md`](../gates/M33/summary.md) · floors: [`floors.md`](../gates/M33/floors.md) (APPROVE) | 2026-10-15 |
| M32 | **CONDITIONAL — accepted by the user 2026-10-11**; G1–G4 all closed (G4: scheduled backup verified 2026-10-12) | [`summary.md`](../gates/M32/summary.md) · floors: [`floors.md`](../gates/M32/floors.md) | 2026-10-12 |

# Dispatch State

**Owner.** Orchestrator. **Updated.** After every task completion and every gate.

Source of truth for "what is next". Subagents never edit this file; they emit handoff notes and the
Orchestrator updates here.

---

## Current milestone

**M34 — Prove retention, close carried debt** (opened 2026-10-16; scope confirmed by the user: hardening and debt, no strategic bet). Tasks in `docs/strategy.md` §11. M33 is archived in [`archive/M33.md`](archive/M33.md).

## Next task

Wave 1 in flight (below). Applied: R-049/R-050/R-051 fixes (`091bb91` SW never routes event streams; `10673fe` flashcard runner walks a deck snapshot; `b12b1b1` admin panel renders up/down per type — Orchestrator mutation-checked the panel test); M34 e2e (`d8fdbfd`: first-run spec on server state; onboarding, study-card feedback, Claude Code availability specs; 155 passing locally ×2; three product bugs pinned as test.fail → R-049…R-051); SEC-013/014 contracts (`ea0bbb0`: secrets-at-rest v2 keeps the OAuth token columns one more release, always NULL; telegram-pairing-code v1 invalidates pending codes rather than hashing in place); SEC-005 secrets at rest (`63a856f`…`5406641`: EncryptedText on the five credential columns incl. `users.mfa_secret`; rotation on raw columns; MFA fail-closed on an unreadable seed; gcal reconnect/revoke rules; migration `b2d4f6a8c0e1` encrypt-up / checked decrypt-down, both live-tested incl. multi-user no-key abort; safety APPROVE, 16 mutants, 740 floor + 164 contract tests re-run by the Orchestrator; R-017 and R-046 closed); SEC-008 + BACKEND-012 (`d2f276d`…`8bd9270`: contract tests minus SEC-005's; `stripe_webhook_events` + migration `a1c2d3e4f5a6`; Stripe claim+apply in one transaction, per-customer advisory lock, R4 unlink on account deletion, no Redis in billing; case-insensitive course lookup; `LOGIN_THROTTLE_UNAVAILABLE{action}`; `/api/onboarding`; safety APPROVE with +26 pins, 24/24 mutations caught, 713 floor tests re-run by the Orchestrator; qa integration +13 incl. real-Postgres concurrency; UI: server-side checklist, study-card and quiz feedback, Claude Code option disabled with reason); qa adapter-contract opt-in fixture (`84a3485`); SEC-006 F settings availability (`cd28919`, `f3a43d4`: settings read schema reports `claude_code_available` + reason; saving or testing claude_code refused with 422 while unavailable; stored values never rewritten); SEC-006 F devops follow-ups (`93dcaca`: deployment "AI pool user" section with host actions, compose comments, `.env.example` opt-in line, preflight warnings, uid/gid 999 pinned in the Dockerfile; backlog: drop the inert `/root/.claude/*` mounts once safety relaxes ALLOWED_TARGETS); SEC-006 option F (`4cb8477`…`1766c17`: non-root AI pools, adapter refuses the CLI on non-root multi-user workers, +103 floor pins, 37 spawn pins repaired, threat model; safety APPROVE, 690 floor tests re-run by the Orchestrator); R-046 / C6 (bound SQL values kept out of error logs: `hide_parameters=True` on the app engine + log redaction strips `[parameters: …]`; 3/11 tests red with the fix reverted — `alembic/env.py`'s engine is SEC-005's `data` step); contracts amended per safety C3–C7 (`ead3e41`) + held tests repointed (`1798333`); ADR 0005 amendment (`8c25495`); AI-010 index split end to end (`a59636c`…`a842b60`: backend embed/store split, safety re-pins incl. `aembed_texts` and a worker-only chunk-store pin, pipeline switch, `_Precomputed` removed) with SEC-009 backend bits (template-only email logs, typed admin feedback view, no question text in qa logs, no model text in parsing logs, `proof.py` removed); SEC-005/008 contract review APPROVE-WITH-CHANGES (`4bce153`; floor-2 red pin held on `hold/m34-floor2-pin`); SEC-009 N-1 (`seed_e2e.py` refuses without `STUDYAIO_E2E_SEED=1` set by its fixture, and on a non-local database host; CI host `postgres` allowed); contracts (`4371b29`, amended `a2accb0`: models.secrets-at-rest v1 incl. `users.mfa_secret`, models.stripe-webhook-events v1, api.ai_feedback stays v1, api.onboarding v1, core.login-throttle-metrics v1, api.study-items v2) with red tests held on `hold/m34-contract-red` (`5d542b1`, `1437546`) for the implementers; ADR 0003 refresh (`110f84b`); FRONTEND-011 (`1eb41a5`: Sentry chunk 482 → 87 KB by importing only the used functions; QuickCaptureModal test deterministic, 20/20 under load), SEC-007 devops part (`8c64d1c`: pip-audit pinned, deploy key check round-trips the key — host deploy.sh reinstall needed at next deploy). Then: SEC-005 + SEC-008 implementation (`data`, `backend`) against the architect's red contract tests; BACKEND-012; AI-010 ai half (drop `_Precomputed`); SEC-007 fastapi cap lift (`backend`); safety review. Time-bound: M34-OPS-001 D7 readout from 2026-10-22, M34-OPS-002 D30 from 2026-11-14, M34-OPS-004 on first prod targeted generation.

## Active

| Task | Owner | Dispatched | Worktree |
|---|---|---|---|
| Un-pin the three bug e2e specs (fixed in `091bb91`, `10673fe`, `b12b1b1`) — e2e red until this lands | `qa` | 2026-10-16 | isolated |
| SEC-013 + SEC-014 floor review (code held: `d766b8c`, `c597a77`, `31bcb3a`; qa integration `60f6a3d`) | `safety` | 2026-10-16 | isolated |
| Log redaction fix (`[parameters: redacted]` re-match) + Stripe customer ids out of billing logs | `backend` | 2026-10-16 | isolated |
| SEC-007: lift `fastapi <0.137` (own venv; prove the route sweep isn't vacuous) | `backend` | 2026-10-16 | isolated |
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
| M34-OPS-003 (M33 C3): first nightly backup under the non-root maintenance pool | Orchestrator | — (prod check) | 2026-10-16 02:00 UTC run: db + data archives written, owned by uid 999; `run_backup` status ok in 23 s; `studyaio_backup_last_success_timestamp_seconds` advanced | 2026-10-16 |


## Blocked

| Task | Owner | Blocked on | Since |
|---|---|---|---|

## Open gates

| Gate | Verdict | Summary | Date |
|---|---|---|---|
| M33 | **CONDITIONAL — accepted by the user 2026-10-15**; C1 D7 readout (≥ 2026-10-22), C2 D30 readout (≥ 2026-11-14), C3 first non-root nightly backup (2026-10-16), C4 first prod targeted generation cites valid pages | [`summary.md`](../gates/M33/summary.md) · floors: [`floors.md`](../gates/M33/floors.md) (APPROVE) | 2026-10-15 |
| M32 | **CONDITIONAL — accepted by the user 2026-10-11**; G1–G4 all closed (G4: scheduled backup verified 2026-10-12) | [`summary.md`](../gates/M32/summary.md) · floors: [`floors.md`](../gates/M32/floors.md) | 2026-10-12 |

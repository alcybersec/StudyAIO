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

**M33 S1 complete and deployed (2026-10-12):** GL#33–#38 closed (MR !38, !39, !40; `main` @ `0869544`). M32 gate conditions G1–G4 all closed. Next: **M33 S2 — weak-spot engine**, starting with M33-S2-ARCH-018 (ADR 0007), which needs the user's acceptance before S2 implementation.

## Active

| Task | Owner | Dispatched | Worktree |
|---|---|---|---|
| M33-S2-DATA-019 (GL#40: weak-spot storage, migration; lands with the red storage contract test) | `data` | 2026-10-15 | isolated |
| M33-S2-FRONTEND-022 (GL#43: Study tonight card, mastery heatmap, diagnostic, practise-this-week; built against api.weak-spots v1) | `frontend` | 2026-10-15 | isolated |

**GL#31 (2026-10-10):** chat follow-ups lose course/week scope (prod repro; a course's week 3 has 8 indexed chunks) — pulled into M32 wave 1 as M32-S4-BACKEND-023 (audit AI-06 overlap).

**M32 GitLab issues (2026-10-10):** GL#11–#30 = M32-S4-BACKEND-001 … M32-S4-QA-020 in §11 order (labels `M32`, `audit-2026-10`). Queued: AI-007 (AI-03, after wave 1), BACKEND-009 (QUOTA-01/COST-01; PROD-08 decided: beta users get Pro).

## Completed

_Rows for the milestone just closed are moved to `docs/plan/archive/<id>.md`
at its gate, leaving one pointer line here._

- M31 — Maintenance: [`archive/M31.md`](archive/M31.md) (closed 2026-10-08, CONDITIONAL, C1–C6 → M32)
- M32 — Safe to grow: [`archive/M32.md`](archive/M32.md) (closed 2026-10-11, CONDITIONAL accepted; 71 rows; G4 → M33)

| Task | Owner | Branch | Evidence | Completed |
|---|---|---|---|---|
| M33-S2-ARCH-018 (GL#39: ADR 0007 weak-spot engine — accepted by the user 2026-10-15 with defaults; 4 contract entries; red contract tests held for their implementers) + BACKEND-051 (R-041: scoped questions bypass the relevance floor, overview questions get the week summary; deployed `b8d7e3a`) | `architect`, `backend` | → `main` `b8d7e3a` (MR !41) | ADR green-state `make test` exit 0; red tests `22 failed, 10 passed, 8 errors` (all not-implemented). Chat fix: red-first test on the prod scores; Orchestrator revert check of the summary-lookup wiring → fails on the `user_id` line; pipeline #651 all 8 jobs success; prod health 200 | 2026-10-15 |
| GL#34 close-out + hardening: summarize v2.5 (MR !39) and summary temperature 0.2, eval baseline refreshed + citation gate, moving-window rate limits (SAFETY-050 pins), flaky-test fixes, deploy keeps 2 app releases (MR !40) | `ai`, `backend`, `devops`, `safety` | → `main` `85fb049`, `0869544` | Live eval, 2 runs/case: mean faithfulness 0.983, citation 91%, 0 broken footers; dp_knapsack exception recorded. Pipelines #642 (backend-tests flake, retried) and #646: all 8 jobs success; `main` #647 success. Prod: `0869544`, temperature 0.2, moving-window, 2 app releases on disk (16 GB free). First deploy refused by the disk guard (7 GB < 8 GB) → old images removed, retention fixed | 2026-10-12 |
| M33 S1 (GL#33–#38): AI-013 cited/faithful summaries (prompt v2.3, page markers, citation metrics — live acceptance pending), BACKEND-014 relevance floor + follow-up retrieval, BACKEND-015/016 AI feedback + usage events + retention readout, BACKEND-017/036 consent gate + profile version + email-free logs, BACKEND-038 / AI-039 redaction holes F1/F2, FRONTEND-035/037 consent dialog (accurate disclosure), feedback, citation chips, admin panels, QA-034/041/042 integration + e2e, SAFETY-033/040 | `ai`, `backend`, `frontend`, `qa`, `safety` | → `kit/retrofit` `24df70b`, MR !38 | **Orchestrator full run on `60fea1c`:** ruff clean; unit 89.35% `3552 passed`; floor 97.62% `534 passed, 1 skipped`, 0 xfail; integration 83.55% `590 passed`; evals `RESULT: PASS`; frontend `697 passed`; leak grep 0 (tree + messages). Pipeline #625: e2e-tests failed (register rate limit exhausted by the new spec) → QA-042. **Pipeline #626 on `24df70b`: all 8 jobs success by name.** Safety APPROVE, no veto | 2026-10-12 |
| M33-S1-DATA-031 (schema `ai_feedback`, `usage_events`, `users.ai_processing_consent_*`; migration `e5b7d2c94a08`) + M33-S1-AI-012/012b + DEVOPS-032 (GL#33: 21 synthetic cases, offline `--check` CI gate `summary-eval`, regression semantics; **measured baseline on the production model: faithfulness 0.878, coverage 0.993, structure 90%**) | `data`, `ai`, `devops` | → `kit/retrofit` (see log) | Migration up/down/up on pg16, single head; Orchestrator: `python -m evals --offline --check` → `RESULT: PASS` (2 known structure WARNs); `glab ci lint` valid; leak grep 0 on files + messages. Live run: 22 provider calls (1 aborted + 21) | 2026-10-11 |

## Blocked

| Task | Owner | Blocked on | Since |
|---|---|---|---|

## Open gates

| Gate | Verdict | Summary | Date |
|---|---|---|---|
| M32 | **CONDITIONAL — accepted by the user 2026-10-11**; G1–G4 all closed (G4: scheduled backup verified 2026-10-12) | [`summary.md`](../gates/M32/summary.md) · floors: [`floors.md`](../gates/M32/floors.md) | 2026-10-12 |

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

**M33 S2 complete and deployed (2026-10-15)** — weak-spot engine live on prod (`main` @ `569789f`, MR !42; GL#39–#45 closed). Next: **M33 S3 — retention UX and debt** (GL#46–#51: onboarding, upload progress across navigation, edit AI cards/quiz items, course/week picker, async embedding, separate Celery queues) and GL#52 (chat-delete confirmation).

## Active

| Task | Owner | Dispatched | Worktree |
|---|---|---|---|

Applied to `kit/retrofit`, not yet pushed: BACKEND-027 + FRONTEND-028 backend (`5f32cb4`, `15c2b51`, `3c1ef9c`), GL#52 + FRONTEND-026 (`624d04a`), GL#46 onboarding (`b269d24`), AI-029 (`6688dbb`, `b53bff6`), FRONTEND-028 UI (`7b7e76b`), BACKEND-057 concepts/chat/qa embed off-loop (`19e63f7`, `f102b73`; index embed/store split deferred, `_Precomputed` stays), AI-029b xfail pin dropped (`e093553`, revert-checked), BACKEND-057b chat/qa transaction released before the answer agent call incl. streaming (`6f82886`, `7f27e44`), GL#51 worker routing (`e9cd187`; also registers the previously unregistered `extract_concepts` task and raises the broker visibility timeout to 7200 s). DEVOPS-030 compose split (`aec844a`; tracked deploy.sh pings the three Celery nodes, exit 69 — host copy needs reinstalling). SAFETY-059 S3 floor review **APPROVE** (`d79d4a6`, `85debc6`; docs/gates/M33/S3-safety.md; floor tier 3 red → 0, +15 floor tests). QA-058 integration +22 (666 passed) and e2e +41 (133 passed locally) (`7dc884c`, `70e51e2`; existing specs moved off `networkidle`, which GL#47's open event stream defeats). FRONTEND-061 (`6f212e2`: both MC editor errors shown; quiz result is one `role=status` region; event stream confirmed once per app shell). DEVOPS-060 (`1815812`: `worker-maintenance` runs as uid 999; prod backups dir ACL already grants 999 rwx and data/ is 999-readable — checked, no host change needed). QA-058b (`5a82f34`: e2e fixture lint fix, quiz-result selectors, stale-question bug pinned). FRONTEND-062 (`a564eb5`, `7c6f9e9`: QuizTab answer area and feedback control shared `key={question.id}`, so the old question stayed mounted after Next; predates S3, from 267e9e9). QA-058c (`9cf1e16`: stale-question test un-pinned, 15/15 study-items spec locally). FRONTEND-063 (`c00d1f1`: Russian locale loaded on demand, entry chunk 521 → 393 KB). Full tier run green locally; QA-064 (`278bb4d`: first-run spec deflaked — session minted from the DB, auth config fulfilled statically). Pipeline on `278bb4d`: all 8 jobs green by name. MR !43 merged (`c6d6cee`) and deployed 2026-10-15 (pipeline 677; frontend-checks + dependency-audit flaked once, retried green). Prod verified: all services on `c6d6cee`, three Celery nodes answer, maintenance runs as `studyaio`, queues empty, 0 errors. Host deploy.sh reinstalled (backup kept). Follow-ups on `kit/retrofit`: GL#53 email headers (`f98fedc`, `0be417c`), AppearanceSection deflake (`f1760d2`), AI-067 per-queue exchanges (`5b05ade`, `2bed33a`, R-044). Backlog: `POST /api/assets/flashcards` matches `course_code` exactly while upload placement is case-insensitive — contract silent, pinned as-is.

## Completed

_Rows for the milestone just closed are moved to `docs/plan/archive/<id>.md`
at its gate, leaving one pointer line here._

- M31 — Maintenance: [`archive/M31.md`](archive/M31.md) (closed 2026-10-08, CONDITIONAL, C1–C6 → M32)
- M32 — Safe to grow: [`archive/M32.md`](archive/M32.md) (closed 2026-10-11, CONDITIONAL accepted; 71 rows; G4 → M33)

| Task | Owner | Branch | Evidence | Completed |
|---|---|---|---|---|
| M33 S2 — weak-spot engine (ADR 0007): DATA-019 storage (migration `f7c3a9d15e24`), BACKEND-020 scoring/plan/API + batch item fetch, AI-021 targeted generation worker + prompts + evals, AI-053 recovery-race fix (found by QA), FRONTEND-022 Study tonight / Mastery / diagnostic / practise, QA-023 integration + worker e2e + Playwright, QA-055 six-tab mobile spec, ARCH-052 AgentAdapter v2, SAFETY-024 APPROVE (17 mutants), AI-056 live targeted baseline | `data`, `backend`, `ai`, `frontend`, `qa`, `architect`, `safety` | → `main` `569789f` (MR !42) | Pipeline #659 e2e red (5-tab spec) → QA-055; **#660 all 8 jobs success**. Local: unit 89.01% (3910), floor 97.73% (552, no xfail), integration 84.19% (643), both eval gates PASS, frontend 734. Prod: `569789f`, migration head, health 200, recovery beat + targeted task registered, 2 release images. Live targeted eval: on-topic 0.950, citation 0.983 (bar ≥ 0.95), dedup 1.000 | 2026-10-15 |
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

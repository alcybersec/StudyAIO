# M31 — Maintenance · Gate re-run summary

**Date** 2026-10-08 · **Branch** `kit/retrofit` @ `8d9de14` (code; later commits are docs only)
· **Pipeline** GitLab #537 on `8d9de14` · **Kit** 1.10.3 · **Previous run** [`summary.md`](summary.md) (2026-10-04, BLOCK)

**Verdict: CONDITIONAL** — Floors APPROVE (`safety`, veto lifted); Functional met; Tests CONDITIONAL
(`qa`). Advancing the milestone needs the user to accept the conditions below.

---

## Functional

The 2026-10-04 miss and the VETO-lift work, against acceptance. Evidence is in `docs/plan/README.md`
§ Completed (M31-S2 rows), re-run by the Orchestrator where noted.

| Item | Evidence | Met? |
|---|---|---|
| M31-S1-DEVOPS-005: a deliberate floor violation and a deliberate coverage drop each redden the pipeline | #526 `test-floor` **failed** (`Floor 2: credential committed to the tree: docs/redproof/sentinel.txt:1`); #527 `backend-tests` **failed** (`FAIL Required test coverage of 75.0% not reached. Total coverage: 61.42%`). Read by job name. #525 exposed a false green (no git in image), fixed (`cbd7d72`, `ffe396d`). Throwaway branches deleted | **Met** |
| QA-004 pipeline half | Same as above (#527) | **Met** |
| Run `tests/contracts` in CI | #537 `backend-tests` contracts step `25 passed` | **Met** |
| Runbook: `make test-floor`, tiers, `coverage-tier.py` | `docs/developer_guide.md` § Coverage Tiers (`d338dc2`) | **Met** |
| User rulings R-007 ×4, R-004 | `docs/decisions.md` § Rulings; ADR 0004 + 0005 Accepted | **Met** |
| ARCH-001 gate question: user accepts ADR 0002 (module boundaries) | Still **Proposed** | **Open** (condition C1) |

## Tests

From `qa` (review mode) and the Orchestrator's own runs.

```
Pipeline #537 @ 8d9de14 (by job name, all success, none skipped)
backend-tests      Required test coverage of 75.0% reached. Total coverage: 87.18%
                   2369 passed · golden 317 passed · contracts 25 passed
test-floor         Required test coverage of 95% reached. Total coverage: 97.32%
                   72 passed
integration-tests  Required test coverage of 70% reached. Total coverage: 87.54%
                   523 passed, 6 xfailed
e2e-tests          54 passed, 10 skipped
frontend-checks    Tests 614 passed (614)
python-lint        success

Orchestrator, local, kit/retrofit @ 049cb2e (same code as 8d9de14):
make test              2711 passed, 87.18% · floor 72 passed, 97.32%
make test-integration  523 passed, 6 xfailed, 87.54%
```

Strict xfails: 22 → **6**, 0 XPASS, none in the floor tier. The 6 pin R-016 functional bugs:
account deletion FK (×2, blocks the floor-4 sanctioned erasure path), billing free tier 500, gcal first
sync 400, MFA disable 500, achievement notification never created.

Gaps (not passes): 10 conditional e2e skips (unchanged); R-019 flake risk (did not show in #537).

`qa` recommendation: **CONDITIONAL**.

## Floors

**`safety` verdict: APPROVE** — see [`floors-rerun-2026-10-08.md`](floors-rerun-2026-10-08.md). The
VETO of 2026-10-04 is lifted. All five lift items met, each with a test first shown red. `safety`'s
own mutation pass: 17/18 reverted fixes redden the tier; the survivor (global `AgentError` handler,
shadowed by the concepts route's own catch) was checked by hand and holds in the code (F-1).

## Operational

- **Scope of change** vs `origin/main`: services (study, qa, courses, gamification, settings, summary,
  course, asset, srs, exam, xp, analytics, export, …), `main.py` handler, agents (redaction),
  pipeline (classify, summarize, notification_tasks), extractors (`txt`), UI (leaderboard toggle),
  one migration, CI, Makefile, docs, tests.
- **Data model:** migration `e3a7c1f95b28` — additive only (`summary_versions`, `archived_at` on
  flashcards/quiz_questions, `user_settings.leaderboard_opt_in`). Downgrade drops retained history
  (documented in the migration). Backup coverage: new table is in Postgres, covered by the existing
  dump.
- **Behaviour changes users will see:** leaderboard hidden unless opted in; concept extraction AI
  failure returns 502 with a generic message; archived cards/questions 404 on review/answer.
- **Metrics/logs:** no new stage. Changed error paths log redacted text or `detail="withheld"`.
- **Rollback:** `kit/retrofit` is not merged to `main`; prod runs `main` images. Rollback = do not merge,
  or revert the merge commit and `alembic downgrade -1` (loses retained versions created since).

## Verdict

**CONDITIONAL.** No dimension failed. To advance M31, the user accepts these conditions, each owned and
scheduled into M32 (a condition that survives two milestones becomes a BLOCK):

| # | Condition | Owner |
|---|---|---|
| C1 | User accepts or amends ADR 0002 (module boundaries) | user → `architect` |
| C2 | R-016: fix the 6 pinned bugs, account-deletion FK first (it blocks floor 4's sanctioned erasure path) | `backend` |
| C3 | 10 conditional e2e skips: make CI seed/auth deterministic, or accept on record | `qa`, `devops` |
| C4 | F-1: pin the global `AgentError` handler directly | `safety` |
| C5 | F-3 / R-020: account purge misses summary blobs of already-deleted courses (incl. retained versions); ADR 0004 #1 "sweeps the user's prefix" is wrong | `backend`, `architect` |
| C6 | F-4 / R-021: scoped service functions default `user_id=None` and skip the filter | `backend`, `safety` |

Housekeeping, not conditions: F-2 stale "RED until" notes in `FLOORS.md` (`safety`); ADR 0003 header
still calls ADR 0005 "(proposed)" (`architect`); R-019 flake triage (`frontend`); GL#10 AI chat
(course/week scope, citation mismatch, test intent).

**Process note.** Isolated worktrees are cut from `main`, not the integration branch; every M31-S2
dispatch had to fast-forward first (one ran on `main` until told). Two backend memory notes were lost
when the Orchestrator removed a worktree before syncing its gitignored `.claude/agent-memory/`.

**User decision (2026-10-08):** conditions C1–C6 accepted; M31 closed; C1–C6 carried into M32 S1
(`docs/strategy.md` §11 M32). ADR 0002 (C1) left Proposed pending the user's review.

Signers:

- Orchestrator — CONDITIONAL, 2026-10-08
- `safety` — APPROVE (`floors-rerun-2026-10-08.md`)
- `qa` — CONDITIONAL (review mode, this file § Tests)
- user — accepted CONDITIONAL, 2026-10-08

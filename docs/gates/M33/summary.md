# Gate M33 — Trust and retention

**Date.** 2026-10-15. **Code under review.** `main` @ `f19efc1` (deployed), `kit/retrofit` @ `d06dbda`
(main plus docs and floor pins). **Signers.** Orchestrator, `safety`, `architect` (ADR 0007 and contract
entries changed in this milestone).

## Functional

Every M33 task in `docs/strategy.md` §11, with its handoff evidence (rows in `docs/plan/README.md` § Completed).

| Task | Evidence | Result |
|---|---|---|
| S1-OPS-004 (M32 G4) | First scheduled `daily-backup` succeeded on prod 2026-10-12; nightly db + data archives present since (5 pairs, latest 2026-10-15 02:00) | PASS |
| S1-AI-012 | 21 synthetic summary cases; offline `--check` gate `summary-eval` in CI with stored baseline and regression semantics | PASS |
| S1-AI-013 | Summaries cite slides/pages (prompt v2.5, temperature 0.2): faithfulness 0.967 vs 0.878 baseline, Key Concepts citation coverage 0.90 (gated); GL#34 closed with the recorded `dp_knapsack` exception (decision 2026-10-12) | PASS |
| S1-AI-014 | Relevance floor plus follow-up retrieval on carried scope; R-041 fix (scoped/overview questions) deployed | PASS |
| S1-BACKEND-015 | AI feedback on summaries, answers, cards and quiz items, per user, admin view | PASS |
| S1-BACKEND-016 | Per-feature usage events (no content, no PII) live on prod since 2026-10-12; D1/D7/D30 cohort readout in admin | PASS |
| S1-BACKEND-017 | Consent recorded before first AI processing (`require_ai_consent`, version 1); email-free logs pinned at floor 2 | PASS |
| S2-ARCH-018 | ADR 0007 Accepted by the user 2026-10-15; 4 contract entries; contract tests green | PASS |
| S2-DATA-019 | Migration `f7c3a9d15e24` (`study_plans`, `targeted_generations`), single head on prod | PASS |
| S2-BACKEND-020 | `weakspot_service` scores/plan/API, owner-scoped with wiring assertions | PASS |
| S2-AI-021 | Targeted generation in the worker, cites slides; live baseline on the production model: citation validity 0.983 (bar 0.95), on-topic 0.950, dedup 1.000 | PASS |
| S2-FRONTEND-022 | Study tonight, mastery heatmap, diagnostic quiz; 375px, en + ru | PASS |
| S2-QA-023 | Integration + worker e2e + Playwright for attempts → scores → plan → targeted quiz | PASS |
| S2-SAFETY-024 | S2 floor review APPROVE | PASS |
| S3-FRONTEND-025 | First-run checklist; empty widgets carry a call to action (GL#46) | PASS |
| S3-FRONTEND-026 | Upload progress persists across navigation (GL#47) | PASS |
| S3-BACKEND-027 | Card and quiz-item edit/delete/add, owner-scoped; edits archive the original, deletes archive (GL#48) | PASS |
| S3-FRONTEND-028 | Optional course/week picker on upload; placed uploads skip classification (GL#49) | PASS |
| S3-AI-029 | No DB transaction across a provider call (pipeline, concepts, chat incl. streaming, Q&A); embedding off the event loop (GL#50) | PASS |
| S3-DEVOPS-030 | Three Celery pools (pipeline / on-demand AI / maintenance), one exchange and routing key per queue, per-node health pings in deploy (GL#51, AI-067) | PASS |

Also shipped: GL#52 (chat-delete confirmation), GL#53 (Message-ID, Date and text/plain on all mail), and a
pre-existing quiz bug (previous question left on screen after Next). No miss.

## Tests

Pasted from the `qa` handoff; evidence on `kit/retrofit` @ `58c4e91` (main `f19efc1` plus docs).

| Tier | Threshold | Result | Verdict |
|---|---|---|---|
| Unit (with golden and contracts) | ≥ 75% | 89.60% (4059 passed) | PASS |
| Integration | ≥ 70% | 88.30% (666 passed) | PASS |
| Floor (`tests/safety`) | ≥ 95% | 97.67% (567 passed, 1 skipped); 97.68% (578 passed) after the gate's two new pins | PASS |
| Frontend unit (vitest) | none | 818 passed | — |
| e2e (Playwright, CI) | none | 134 passed | — |

```
pytest tests/unit tests/golden tests/contracts --cov=app -q
Required test coverage of 75.0% reached. Total coverage: 89.60%
4059 passed, 269 warnings in 524.64s (0:08:44)

pytest tests/safety -q --cov=tests/safety --cov-fail-under=95
Required test coverage of 95% reached. Total coverage: 97.67%
567 passed, 1 skipped, 33 warnings in 492.76s (0:08:12)

PYTEST=<venv>/pytest bash scripts/test-integration.sh
Required test coverage of 70% reached. Total coverage: 88.30%
666 passed, 11 warnings in 496.90s (0:08:16)

npx vitest run
Test Files 111 passed (111) / Tests 818 passed (818)
```

**Pipelines, read by job name.**

- `c6d6cee` (S3 deploy): all jobs succeeded, including `e2e-tests` and `deploy-selfhosted`. `dependency-audit`
  (PyPI read timeout) and `frontend-checks` (locale-test race) failed once and succeeded on retry; the race is
  fixed in `f1760d2`.
- `f19efc1`: all 11 jobs succeeded on the first attempt. Nothing skipped or cancelled.

**Evals.**

- `python -m evals --offline --check`: summary PASS, targeted PASS.
- Summary live baseline (2026-10-12): faithfulness 0.967, coverage 100%, structure 100%, citation coverage
  0.9025. The gate is `max(0.90, baseline − 0.05)`, so headroom is thin.
- Targeted live baseline (2026-10-15): citation validity 0.983, on-topic 0.950, dedup 1.000.

**Golden.** No golden fixture changed in M33.

**Flakes.**

- Fixed: the AppearanceSection locale race, and the first-run spec rate limit plus `route.fetch` teardown.
- Transient: the `dependency-audit` PyPI timeout.
- Open: `QuickCaptureModal.test.tsx` is load-sensitive. It is logged as R-045.

## Floors

**APPROVE** — written by `safety` in [`floors.md`](floors.md), with the threat-model delta in
`docs/security/threat-model.md`. S3 detail: [`S3-safety.md`](S3-safety.md).

## Operational

- **Metrics and logs for new stages.**
  - Weak-spot scoring and targeted generation emit counters and latency labelled `{stage, outcome, error_class}`.
  - The backup task emits `BACKUP_RUNS` and `BACKUP_DURATION`.
  - Usage events and AI feedback are stored per user and read in admin.
  - Each Celery node answers a ping at deploy (exit 69 on silence).
- **Runbook.** `docs/deployment.md` has a "Celery workers and queues" section: pools, queue-depth `LLEN` check,
  single-worker fallback `-Q pipeline,ai_ondemand,maintenance,celery`, maintenance pool user.
- **Rollback.** Deploy keeps 2 app releases and takes a pre-deploy database dump. Migrations in M33 have tested
  downgrades.
- **Backup coverage for the data-model change.** The new tables (`usage_events`, `ai_feedback`, `study_plans`,
  `targeted_generations`) and the new item origin `user` are inside the nightly `pg_dump`.
- **Gap.** The maintenance pool has run as `studyaio` only since today. The first nightly backup under that user
  has not run yet (C3).
- **Prod after the last deploy.**
  - All services run `f19efc1` with 0 restarts.
  - Health is ready.
  - All four queues are empty, each on its own exchange.
  - 0 errors in api, the three workers and beat.

## Milestone additions

| Addition | Evidence | Result |
|---|---|---|
| G4 closed | First scheduled backup verified 2026-10-12 | met |
| Summary faithfulness on ≥ 20 cases in CI with baseline and non-regression threshold | 21 cases, `summary-eval` job, baseline 0.967 | met |
| Summary and Q&A citations grounded and pinned | Citation coverage gated at 0.90; Q&A relevance floor and citation chips pinned by tests | met |
| Per-feature usage events live in prod with a D7/D30 readout | 19 events from 2 of 3 users since 2026-10-12; readout endpoint live | met (readout mechanism); data still thin |
| Weak-spot engine live: plans generated for active users | 1 plan on prod (1 of 2 active users), created 2026-10-15 | partially met — engine live, usage minimal |
| Targeted items cite slides | Live eval 0.983 citation validity; no targeted item generated on prod yet | met by eval; not yet observed on prod (C4) |
| D7/D30 of users with a plan vs without | Not measurable: the engine went live 2026-10-15; D7 exists from 2026-10-22, D30 from 2026-11-14. With 3 users the comparison is descriptive, not causal (ADR 0007: no hold-out until enough users) | not met — time-bound (C1, C2) |
| `safety` APPROVE | [`floors.md`](floors.md) | met |

## Verdict

**CONDITIONAL.** Engineering is complete and floors hold; the retention evidence the milestone is judged by
cannot exist yet.

| # | Condition | Owner | Deadline task |
|---|---|---|---|
| C1 | D7 readout: users with a Study-tonight plan vs without, from the admin cohort readout, reported descriptively | Orchestrator, `backend` | M34-OPS-001 (on or after 2026-10-22) |
| C2 | D30 readout, same comparison | Orchestrator, `backend` | M34-OPS-002 (on or after 2026-11-14) |
| C3 | First nightly `run_backup` under the non-root maintenance pool succeeds (db + data archives written, `BACKUP_RUNS{outcome="success"}`) | Orchestrator, `devops` | M34-OPS-003 (2026-10-16) |
| C4 | First targeted generation on prod observed: items cite pages that exist in their lecture | Orchestrator, `ai` | M34-OPS-004 (first prod use) |

**Carried-condition tally.** No condition has survived two milestones. M32's G4 was carried into M33 and closed
here. Several non-blocking `safety` notes have stayed open since M32 without being gate conditions, listed in
`floors.md` N-6:

- the `fastapi <0.137` cap;
- the deploy key check tests presence only;
- `pip-audit` is unpinned;
- OAuth and calendar tokens are plaintext at rest (R-017);
- Stripe dedupe state lives in Redis;
- the empty `proof.py`;
- the two AI pools still run as root.

Each should either become an M34 task or be explicitly accepted.

**Signatures.** Orchestrator — CONDITIONAL. `safety` — APPROVE ([`floors.md`](floors.md)). `architect` — ADR 0007
and its contract entries accepted 2026-10-15; contract tests green.

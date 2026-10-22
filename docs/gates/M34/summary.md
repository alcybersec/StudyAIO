# Gate M34: Prove retention, close carried debt

**Date.** 2026-10-22.

**Code under review.** `main` @ `b637dd2`, deployed 2026-10-18, and `kit/retrofit` (docs since).

**Signers.** Orchestrator, `safety`, and `architect` (contracts changed: models.secrets-at-rest v1 → v2,
models.telegram-pairing-code v1, models.stripe-webhook-events v1, api.onboarding v1, api.study-items v2,
core.login-throttle-metrics v1; ADR 0003 and 0005 amended).

## Functional

Every M34 task in `docs/strategy.md` §11. Handoff evidence is in `docs/plan/README.md` (Completed and Applied) and in the
per-change safety reviews in this directory.

| Task | Evidence | Result |
|---|---|---|
| OPS-001 (M33 C1): D7 readout | 2026-10-22, counts only. Window is days 1–7 after each user's first plan; no-plan users are anchored on the launch. With a plan: 1 user, active 1. Without a plan: 2 users, active 0. Descriptive only (n=3; ADR 0007 has no hold-out). | PASS |
| OPS-002 (M33 C2): D30 readout | Cannot exist before 2026-11-14. | not yet (C1 below) |
| OPS-003 (M33 C3): first non-root nightly backup | Run at 2026-10-16 02:00 wrote db + data archives owned by the app uid, status ok, `backup_last_success` advanced; nightly since. | PASS |
| OPS-004 (M33 C4): first prod targeted generation cites real pages | No targeted generation has run on prod (0 rows, checked 2026-10-22). Live eval citation validity 0.983 (bar 0.95). | not yet (C2 below) |
| S2-SEC-005: secrets at rest | `EncryptedText` on 5 columns incl. the TOTP seed. Rotation works on raw columns. An unreadable seed fails closed. Migration `b2d4f6a8c0e1` encrypts up and checks before decrypting down; live-tested, including the multi-user no-key abort. `sec005-safety.md` APPROVE. | PASS |
| S2-SEC-006: non-root AI pools | Option F: the pools run as the app uid, and the Claude CLI is refused on non-root multi-user workers; the settings API reports it unavailable. Verified on prod after deploy: uid, data/HOME writable, login readable. `sec006-safety.md` VETO as-is, lifted by option F. | PASS (option B sidecar in backlog) |
| S2-SEC-007: pip-audit pinned, FastAPI cap lifted, deploy key check | pip-audit 2.10.1. FastAPI 0.136 → 0.143, with route walkers on `iter_route_contexts` plus an OpenAPI cross-check; sweep 171/135/113, no drop. deploy.sh round-trips the key (exit 68). `fastapi-lift-safety.md` APPROVE. | PASS |
| S2-SEC-008: Stripe dedupe in Postgres | Claim and apply in one transaction, per-customer advisory lock, account deletion unlinks (no delete). Migration `a1c2d3e4f5a6`. Real-Postgres concurrency tests. `sec008-012-safety.md` APPROVE. | PASS |
| S2-SEC-009: N-1…N-5 + `proof.py` | e2e seed guard; typed admin feedback view; ADR 0003 refreshed; email logs carry the template name only; `proof.py` removed. | PASS (ADR 0003 line column drifted again; see `floors.md`) |
| S2-SEC-013: stop storing OAuth sign-in tokens | Sign-in writes None; migration `c3e5a7b9d1f2` nulls existing values. Prod: 0 non-null tokens. `sec013-014-safety.md` APPROVE. | PASS (column drop = v3, backlog) |
| S2-SEC-014: Telegram codes hashed | SHA-256 digest, looked up by digest in SQL; pending codes invalidated. APPROVE. | PASS |
| S2-SEC-015: Telegram webhook secret | Constant-time compare that fails closed in multi-user mode; registration CLI; bot username; secret validation. Library log caps (F1, F2). `sec015-safety.md` APPROVE. | PASS |
| S3-AI-010: index embed/store split | `_Precomputed` removed; no session across the encode (pinned); safety re-pins incl. `aembed_texts`. | PASS |
| S3-FRONTEND-011: bundle headroom, QuickCapture test | Sentry chunk 482 → 87 KB; test deterministic (20/20 under load). | PASS |
| S3-BACKEND-012: backlog items | Case-insensitive course lookup, `login_throttle_unavailable{action}`, server-side onboarding, study-card and quiz feedback. | PASS |

Also shipped:
- **R-046:** bound SQL values kept out of error logs.
- **R-049:** the service worker held the event stream; this bug was live in prod and is now fixed.
- **R-050:** flashcard runner skipped cards.
- **R-051:** admin panel crashed.

No task missed.

## Tests

From the `qa` handoff. Commands and last lines are run locally on `kit/retrofit` @ `25b8538` (main `b637dd2` + docs).

| Tier | Threshold | Result | Verdict |
|---|---|---|---|
| Unit + golden + contracts | ≥ 75% | 89.91% (4250 passed) | PASS |
| Integration | ≥ 70% | 84.07% (686 passed) | PASS |
| Floor | ≥ 95% | 97.79% (806 passed, 1 skipped; CI 807 passed, 97.85%) | PASS |
| vitest | n/a | 836 passed (113 files) | n/a |
| e2e | n/a | 155 passed (CI, deploy commit); 131 before M34 | n/a |

```
pytest tests/unit tests/golden tests/contracts --cov=app -q
Required test coverage of 75.0% reached. Total coverage: 89.91%
4250 passed, 239 warnings in 584.74s (0:09:44)

pytest tests/safety --cov=tests/safety --cov-report=term --cov-fail-under=95
Required test coverage of 95% reached. Total coverage: 97.79%
806 passed, 1 skipped, 35 warnings in 647.83s (0:10:47)

PYTEST=<venv>/pytest bash scripts/test-integration.sh
Required test coverage of 70% reached. Total coverage: 84.07%
686 passed, 11 warnings in 210.42s (0:03:30)
```

### Pipelines, read by job name

The `main` pipeline that deployed `b637dd2`: all 11 jobs succeeded, none skipped.

Red `kit/retrofit` pipelines during M34, each fixed before deploy:
- **`26f9ab5`, `e2e-tests`:** the first-run spec was stale after the server-side checklist. Fixed in `d8fdbfd`.
- **`4fb7313`, `python-lint`:** CI ruff was ahead of the lock, so every later job was **skipped** — not a pass. Fixed in `a48c72d`, and CI now installs the lock's ruff (`ecacb06`, R-053).

**Open: `25b8538`, `dependency-audit` failed.** pip-audit reports 25 known vulnerabilities, all published after the deploy (the same lock passed on `b637dd2`):
- pillow 12.3.0: 24 advisories, fixed in 13.0.0;
- certifi 2026.7.22: 1 advisory.

Prod runs this lock, and Pillow parses images from uploaded lectures. This is condition C3.

### Evals

The offline `--check` passes. The summary and targeted baselines are unchanged in M34, and no prompt changed.

### Golden

No golden fixture changed.

### Flakes

- QuickCapture: fixed.
- The AppearanceSection locale race: fixed.
- The `dependency-audit` PyPI timeout: transient.

## Floors

**APPROVE**. Written by `safety` in [`floors.md`](floors.md); the threat-model delta is in
`docs/security/threat-model.md`. Per-change reviews:
- [`contracts-safety.md`](contracts-safety.md)
- [`sec005-safety.md`](sec005-safety.md)
- [`sec006-safety.md`](sec006-safety.md)
- [`sec008-012-safety.md`](sec008-012-safety.md)
- [`sec013-014-safety.md`](sec013-014-safety.md)
- [`sec015-safety.md`](sec015-safety.md)
- [`fastapi-lift-safety.md`](fastapi-lift-safety.md)

## Operational

**Metrics and logs for new paths:**
- `studyaio_login_throttle_unavailable_total{action}`
- `studyaio_claude_cli_spawn_refusals_total{stage,outcome,error_class}`
- valueless events for undecryptable secrets, an unavailable MFA seed, calendar reconnect required, and the Telegram webhook (unset secret, registered, failed)
- Stripe customer ids logged as fingerprints

**Library loggers capped at WARNING:** httpx, httpcore, googleapiclient, stripe, requests_oauthlib, oauthlib, botocore, boto3, urllib3.

**Runbook (`docs/deployment.md`):**
- AI pool user and host prep
- Telegram webhook secret and bot username
- three Celery pools
- key rotation (`encrypt-user-secrets`, drop the old key only at `unreadable: 0`)

**Rollback:**
- The deploy keeps 2 releases and takes a pre-deploy dump; one was taken 2026-10-18.
- The downgrades are documented and live-tested:
  - `b2d4f6a8c0e1` decrypts with checks and removes at-rest protection.
  - `c3e5a7b9d1f2` cannot restore nulled tokens.
  - `a1c2d3e4f5a6` drops the dedupe table.

**Backup coverage for the data-model change:** `stripe_webhook_events`, `users.onboarding_checklist` and the encrypted columns are all inside the nightly `pg_dump`. Backups run nightly under the non-root maintenance pool.

**Host changes this milestone, all verified on prod:**
- `data/` and the login dir are owned by the app uid.
- `data/` is on a memberless group with setgid (R-054).
- deploy.sh was reinstalled.

## Milestone additions

| Addition | Evidence | Result |
|---|---|---|
| C1–C4 closed or reported | C1 (D7) reported; C3 (backup) closed; C2 (D30) is time-bound; C4 is not yet observed | partially met |
| Every S2 item closed or explicitly accepted by the user | SEC-005/006(F)/007/008/009/013/014/015 closed; option F accepted by the user 2026-10-16 | met |
| No security note older than one milestone left untallied | Tallied in `floors.md`: every M32/M33 note closed; R-009 and R-010 open since M31 (see tally) | met (tallied) |
| `safety` APPROVE | [`floors.md`](floors.md) | met |

## Verdict

**CONDITIONAL.** The engineering is complete, deployed and verified, and the floors hold. Three conditions remain:

| # | Condition | Owner | Deadline task |
|---|---|---|---|
| C1 | D30 readout, plan vs no plan, descriptive (was M33 C2) | Orchestrator, `backend` | M35-OPS-001 (on or after 2026-11-14) |
| C2 | First prod targeted generation: items cite pages that exist in their lecture (was M33 C4) | Orchestrator, `ai`; needs one real use | M35-OPS-002 (first prod use) |
| C3 | Dependency advisories: pillow ≥ 13.0.0 and certifi bumped, pip-audit clean, deployed | `backend`, `safety` | M35-SEC-001 (dispatched 2026-10-22) |

### Carried-condition tally

**Two conditions have now survived two milestones.** C1 (D30) and C2 (targeted generation) were M33's C2 and C4, were
carried through M34, and now go into M35. Neither is an engineering miss:
- D30 is a calendar date.
- C2 needs a real student to press "Practise weak spots" once.

Two risks have been open since M31, more than two milestones:
- **R-010:** `review_items` and `quiz_attempts` have no `user_id`; they are scoped through joins. Needs a decision: add the column, or rule a permanent exception.
- **R-009:** no secret scanning in CI. Needs a decision: add it, or close as superseded by the floor-2 tree scan.

**Signatures.** Orchestrator: CONDITIONAL. `safety`: APPROVE ([`floors.md`](floors.md)). `architect`: the contract entries
above were reviewed by `safety` before implementation, and contract tests are green.

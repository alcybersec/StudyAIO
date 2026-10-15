# M33 gate: Floors dimension

**Reviewer:** `safety` (veto role), review mode · **Date:** 2026-10-15
**Tree:** `kit/retrofit` @ `58c4e91`. The gated code is `main` @ `f19efc1`, deployed to prod on 2026-10-15 by
`deploy-selfhosted` in `main` pipeline #681. `git diff --stat f19efc1 58c4e91` shows two files,
`docs/plan/README.md` and `docs/risk-register.md`. **Range:** everything after the M32 gate commit (`5418190`), 132
commits excluding merges: S1, S2, S3 and the S3 tail (AI-067, GL#53, FRONTEND-063/066, QA-064). This review changes no
`app/` code. It adds two floor pins under `services/app/tests/safety/**` and the M33 delta in
`docs/security/threat-model.md` (§6).

Floor text is quoted from `docs/strategy.md` §6, as amended by ADR 0003, ADR 0004 and ADR 0005. The floor-to-test map
is `services/app/tests/safety/FLOORS.md`. As at M31 and M32, this file judges whether each floor **holds in the
code**, which is a stricter test than whether the tier is green.

## 1. Run evidence

### Local, on `58c4e91` (the main checkout's venv, read-only)

`make test-floor`'s command. `coverage-tier.py floor` returns 95. First, the tier as it stood:

```
$ cd services/app && python -m pytest tests/safety -v --cov=tests/safety --cov-report=term-missing --cov-fail-under=95
TOTAL                                                    6937    259    96%
Required test coverage of 95% reached. Total coverage: 96.27%
=========== 567 passed, 1 skipped, 32 warnings in 417.12s (0:06:57) ============
EXIT=0
```

(The 96.27% is low because this review's new test file appeared on disk partway through the run. Coverage counted it
as unexecuted source. CI's 97.76% on the same tree is below.)

After this review's two pins:

```
$ cd services/app && python -m pytest tests/safety -v --cov=tests/safety --cov-report=term-missing --cov-fail-under=95
TOTAL                                                    6941    161    98%
Required test coverage of 95% reached. Total coverage: 97.68%
=========== 578 passed, 1 skipped, 33 warnings in 586.30s (0:09:46) ============
EXIT=0
```

578 is the earlier 567 plus 11 new cases: 9 mail cases and 2 delivery cases.

The skip is `test_floor2_setup_script_refuses_to_run_as_root`, which is `skipif(os.geteuid() != 0)`. CI runs as root
and runs it, which is why CI shows 568 passed and 0 skipped.

`ruff check tests/safety/` → `All checks passed!` · `ruff format --check tests/safety/` → `34 files already formatted`.

`make test` was not run, because its `bootstrap` step would build a venv in the worktree, and this review installs
nothing. The floor tier above is `make test`'s second half. CI's `backend-tests` covers the first half (below).

### Pipelines, read by job name

`glab api "projects/:fullpath/pipelines/<id>/jobs?include_retried=true"`. The `kit/retrofit` head `58c4e91` is pipeline
#683, status `success`.

**`main` @ `f19efc1`, pipeline #681, `success`.** No job is skipped, manual or retried.

| Job | Status, from the trace |
|---|---|
| `python-lint` | success |
| `backend-tests` | success: unit `Total coverage: 89.35%`, `3649 passed`; golden `317 passed`; contracts `93 passed` |
| `summary-eval` | success |
| `test-floor` | success: `Required test coverage of 95% reached. Total coverage: 97.76%`, `568 passed` |
| `integration-tests` | success: `Total coverage: 84.22%`, `666 passed` |
| `dependency-audit` | success: `No known vulnerabilities found`; `0 unallowlisted high/critical npm advisories` |
| `frontend-checks` | success |
| `e2e-tests` | success: `134 passed` |
| `build-api`, `build-ui` | success |
| `deploy-selfhosted` | success: `Deploy complete: f19efc11ca8a… (tag f19efc1)` |

## 2. Mutation check (this review)

Script: `scratchpad/mutate_m33.py`. It is not committed, because it edits other roles' `app/` code. It applies one
mutant at a time to a scratch copy of the tree at `58c4e91` with this review's pins added. It runs the named floor
files before and after each mutant (`pytest -x`, so a red run stops at its first failure) and restores the file. The
copy has no `.git`, so its compose-file lister is patched to a glob for the two pool rows. That patch is in the scratch
copy only.

| Mutant (the fix reverted) | Floor selection | Control | Mutant |
|---|---|---|---|
| **F1 study items:** `asset_service._owned_item` drops `Course.user_id == user_id` (`asset_service.py:273`) | `test_floor1_study_item_crud.py`, `test_floor1_tenant_isolation.py` | 31 passed | **1 failed** |
| **F1 upload placement:** `get_or_create_course` matches `upper(code)` only (`course_service.py:85`) | same | 31 passed | **1 failed** |
| **F1 weak spots:** `get_targeted` loses `TargetedGeneration.user_id == user_id` | `test_floor1_targeted_generation.py`, tenant sweep | 29 passed | **1 failed** |
| **F1 AI feedback:** chat-target ownership dropped from `_owned_chat_course` | `test_floor1_ai_feedback_usage.py`, tenant sweep | 46 passed | **1 failed** |
| **F3 consent:** `POST /weak-spots/targeted` loses `Depends(require_ai_consent)` | `test_floor3_ai_consent_gate.py` | 21 passed | **1 failed** |
| **F3 adapter:** a sixth request-time `get_agent` site in `api/weakspots.request_targeted` | `test_floor3_ai_via_adapter.py` | 13 passed | **1 failed** |
| **F4 study items:** `archive_flashcard` does `session.delete(card)` instead of setting `archived_at` | `test_floor4_user_data_never_lost.py`, CRUD pins | 33 passed | **1 failed** |
| **F4 targeted:** `populate_existing` removed from `_persist` (`targeted_task.py:329`) | targeted pins, floor 4 | 31 passed | **1 failed** |
| **F2 pools:** `extract_concepts` routed to `maintenance` | `test_floor2_worker_pool_credentials.py` | 6 passed | **1 failed** |
| **F2 pools, AI-067 reverted:** `Queue(name)` again (`worker.py:119`) | same | 6 passed | **1 failed** (the new `declared-address` pin; the `send_task` case passes, which matches R-044's "latent") |
| **F2 mail:** `email_sent` also logs the plain body | `test_floor2_email_delivery_logs.py`, `test_floor2_no_email_in_logs.py` | 39 passed | **1 failed** (new pin) |
| **F2 mail:** `email_send_failed` also logs `to=to_email` | same | 39 passed | **1 failed** |

**No survivor.** Before this review, two of the twelve had no floor-tier pin. The AI-067 revert was pinned only in
the unit tier (`tests/unit/pipeline/test_queue_bindings.py`). The mail-body leak was pinned nowhere: the AST sweep
watches addresses, not tokens or bodies. §5 lists the two new pins.

**Floor-1 sweep counts (R-040 rule).** No dependency moved in M33 (`git diff 5418190 HEAD` is empty for the
requirements, the lock and `package*.json`), so the lift rule did not apply. I took the counts anyway, through a
scratch test that calls `_sweep_routes` and `_run_sweep`:

```
COUNTS api_routes=169 swept_pairs=133 owned_reached=111 violations=['GET /api/gamification/leaderboard']
```

M32 had 149, 115 and 99. The growth is the M33 routes (weak spots, study plan, study items, feedback, usage events),
and none dropped. The one violation is the ruled opt-in leaderboard (`SWEEP_OPT_IN_CROSS_USER`).

## 3. Prior M33 `safety` verdicts rolled up

| Task | Scope | Verdict | Status at the gate |
|---|---|---|---|
| M33-S1-SAFETY-005 | G1: test-ai quota, metering, rate limit; metrics labels | APPROVE | Pins green; M32 N-1 resolved |
| M33-S1-SAFETY-033 | Consent gate, AI feedback, usage events, retrieval floor, email-free logs | APPROVE with F1/F2 strict xfails | F1 and F2 closed (SAFETY-040) |
| M33-S1-SAFETY-040 | F1 traceback redaction, F2 worker logging | APPROVE | Plain floor tests; green |
| M33-S1-SAFETY-050 | SEC-10 moving window, login throttle under the fake | APPROVE | Green |
| M33-S2-SAFETY-024 | Weak-spot engine, targeted worker, ADR 0007 | PASS with notes, after the floor-4 defect was fixed in AI-053 | Green; re-mutated above |
| M33-S3-SAFETY-059 (`docs/gates/M33/S3-safety.md`) | Study-item CRUD, upload placement, three worker pools | APPROVE | Green; re-mutated above |

**No `safety` VETO is open.** There are no `xfail` markers in the backend tests, and no `test.skip`, `fixme` or `fail`
in e2e (`grep -rn "xfail" services/app --include=*.py`, `grep -rnE "test\.(skip|fixme|fail)\(" services/ui/e2e`).
The only matches are prose in `FLOORS.md` and docstrings.

## 4. Per-floor judgement

### Floor 1: tenant isolation

> an authenticated endpoint never returns or mutates another user's rows; every user-owned query filters on user_id

**Holds in the code: YES.**
- The route sweep covers 133 method+path pairs, and 111 of them reach owned tables (§2). It includes every new M33
  route. The function-level unscoped-query and optional-caller detectors are green.
- **Consent, feedback, usage (S1).** Votes land only on the caller's own targets, and a foreign target gets the same
  404 as a missing one (`test_floor1_ai_feedback_usage.py:138`). Usage events are always keyed on the caller
  (`:289`). The admin aggregates require the admin role and project no user id (`:368`, `:424`, `:473`). Re-mutated:
  the chat-target ownership mutant is red.
- **Weak spots and the targeted queue (S2).** Every service function takes `user_id` and joins `courses.user_id`. The
  worker takes the row id only and acts as `row.user_id` (`test_floor1_targeted_generation.py:277`, `:317`, `:333`).
  The daily cap counts only the caller's rows (`:533`). Re-mutated: `get_targeted` unscoped is red.
- **Study-item CRUD and upload placement (S3).** Foreign, missing and archived items get one identical 404
  (`test_floor1_study_item_crud.py:155`). Create cannot target a foreign course or lecture (`:176`). Placement never
  resolves a foreign course (`:269`). Re-mutated: both are red.
- **QA-064 session minting** is test-only, and gives no cross-tenant path in a deployed instance (§6, item 7).
- Still open, not red: R-010 (`review_items` and `quiz_attempts` are scoped by join).

### Floor 2: no secrets in the tree

> no plaintext credentials, tokens or keys committed, and per-user AI credentials are never logged or returned by the API

**Holds in the code: YES.**
- The committed-file scan ran with git present, locally and in CI. M33 committed no credential. The only key-like
  literals in tracked files are the M32-era CI placeholder `JWT_SECRET_KEY` for the throwaway e2e database, and the
  committed default that production refuses at startup. Neither is a live credential.
- Per-user AI credentials: M33 added no route that reads `user_settings` credentials. Encryption at rest, the
  never-echoed PUT, GET and export, adapter-boundary redaction and the global `AgentError` handler are unchanged and
  green. The targeted worker uses the row owner's config through `get_agent`. Its `error_code` is a fixed literal, and
  `error_class` is a type name (S2 delta 3).
- **Three worker pools (GL#51).** The Claude login is mounted only in `worker` and `worker-ondemand`, which is the
  exact allowlist `CLAUDE_LOGIN_SERVICES`, tied to `_QUEUE_TASKS` by the call graph. `worker-maintenance` holds no
  login and, since `1815812`, runs as `studyaio:studyaio` (`docker-compose.yml:176`). New this gate: the delivery pin
  shows that a message for any AI task reaches only its routed queue, both through Celery's publish and through the
  queue's declared address. It is red on the AI-067 revert, which the floor tier did not catch before.
- **Outgoing mail (GL#53).** `email_sent` (`email_service.py:164`) and `email_send_failed` (`:178`) log the subject
  only. `Message-ID` uses the sender's domain only. The new text part puts each reset, verification or invite token in
  the message a second time, but in no log. New this gate: a runtime pin sends each token-bearing mail through the
  real logging configuration at DEBUG, on success and on two failure shapes that name the recipient. The stream
  carries neither the address, the token nor the body. It is red on both logging mutants.
- **Email-free logs (SEC-08).** The call-site sweep, the redaction processor and filter, and F1/F2 are green.
- Outside the floor's literal text, still open: OAuth and calendar tokens are plaintext at rest (R-017, M32 N-7).

### Floor 3: AI only via the adapter (ADR 0003, ADR 0005)

**Holds in the code: YES.**
- The request-time `get_agent` sites are `api/qa.ask_question`, `api/settings.test_ai_connection`,
  `chat_service.send_message`, `chat_service.stream_message` and `concept_service.extract_and_save_concepts`. That is
  five, and it equals `REQUEST_TIME_GET_AGENT_CALL_SITES` in ADR 0003. The ADR is unamended since M32
  (`git log 5418190..HEAD -- docs/adr/` shows only ADR 0007). The `get_embedding_provider` sites are unchanged.
- The one new `get_agent` caller, `app/pipeline/targeted_task.py`, is a registered Celery task. ADR 0007 Decision 5
  records that it adds no request-time site. The targeted route enqueues and never builds an agent.
- **Consent (SEC-08)** precedes every AI spend and enqueue, and the gated route set is derived from code. Re-mutated:
  the targeted route without the dependency is red. A sixth request-time site is red as well.
- The ADR's `file:line` column has drifted (for example, `qa.py:85` is now `:110`). The pin compares
  `(module, function)` pairs, so it is unaffected. The column is for `architect` to refresh.

### Floor 4: user data is never lost (ADR 0004)

**Holds in the code: YES.**
- **Study-item edit and delete** archive the original and never delete it. Reviews and attempts stay on the original
  (`test_floor1_study_item_crud.py:214`, `:234`, `:249`). `asset_service` has no SQL DELETE, and the floor-4 delete
  inventory is exact and green. Re-mutated: the hard-delete mutant is red.
- **Targeted generation** is insert-only. Regeneration never archives targeted items
  (`test_floor1_targeted_generation.py:437`). A recovered row gets nothing inserted later (`:375`). Re-mutated: the
  missing `populate_existing` is red.
- **Pipeline regeneration** (`b53bff6`) saves both sets after both AI calls, and archives prior items rather than
  deleting them. **Re-embed** writes new chunks and deletes old ones in one transaction after the vectors exist.
- **Account deletion** is still the only path that removes `data/` content. The new tables (`ai_feedback`,
  `usage_events`, `study_plans`, `targeted_generations`) each have a non-null `user_id`. The account purge
  (`account_service.delete_user_account`) walks every table and matches rows on it, so these go with the account,
  which the floor permits.
- `scripts/restore.sh` stops and restarts all three pools around a restore, so no pool writes during it.

## 5. Changes made in this review (`safety` paths only)

- `services/app/tests/safety/test_floor2_worker_pool_credentials.py`: new
  `test_floor2_an_ai_task_message_reaches_only_a_pool_with_the_login[send_task|declared-address]`. Red on the AI-067
  revert, green on `58c4e91`.
- `services/app/tests/safety/test_floor2_email_delivery_logs.py` (new): nine cases covering three token-bearing mails,
  success and two failure shapes. Red on both mail-logging mutants, green on `58c4e91`.
- `services/app/tests/safety/FLOORS.md`: maps both pins and records the gate mutations.
- `docs/security/threat-model.md`: the M33 gate delta, three new asset rows, and the B4 residual updated for the
  pool split.

## 6. Threat-model delta (M33)

The full text is in `docs/security/threat-model.md` §5, "2026-10-15, M33 gate", which follows the S1 and S2 deltas
written during the milestone. Summary by new surface:

| Surface | Judgement | Residual |
|---|---|---|
| AI-processing consent (SEC-08) | A 403 precedes every spend and enqueue. The route set is derived from code. Single-user mode is the only bypass | The disclosure wording was tightened in S1 (`a170a45`) |
| AI feedback | Votes land only on the caller's own targets; the 404 is no oracle; the comment is never logged and never copied into usage events | `recent_negative` hands admins free text with a `course_id`, which an admin can trace to an owner; the response is an untyped `list[dict]` |
| Usage events | Keyed on the caller; property keys allowlisted; scalar values only; admin views carry no user id | none new |
| Weak-spot APIs and study plan | Owner-joined everywhere; a foreign generation id looks the same as a missing one | Daily cap is count-then-insert (one extra generation per race; quota still bounds spend) |
| Targeted generation queue | Worker-only AI, acts as the row owner, insert-only, recovery re-checked under lock | Prompt block delimiters are not escaped; the reach is self-only |
| Study-item CRUD | Owner-scoped, soft delete, no oracle | none |
| Upload placement | Course found or created for the caller only, case-insensitively, under the caller's course quota | none |
| Three worker pools and the credential split | Login only where `get_agent` is reached; delivery now pinned (AI-067); `worker-maintenance` non-root | The AI pools still run as root for the login mounts; every pool gets `.env` |
| Outgoing mail (GL#53) | Tokens are in two MIME parts now, and in no log (pinned) | Pre-M33: the pipeline-complete and exam-reminder subjects (file name, course code, exam title) reach the `email_sent` line |
| e2e session minting (QA-064) | Test-only: in no image, and called only by Playwright fixtures in the CI job against its own database. Without the production signing key it signs with the committed default, which production refuses | No in-script guard. Pointed at a real database, `session`/`user` reset that user's password and print tokens for whatever key is in the environment |
| Russian locale on demand | Fixed map from a supported tag to a bundled chunk | none |

## 7. Open non-blocking notes, with owners

| # | Note | Owner |
|---|---|---|
| N-1 | `seed_e2e.py` has no guard against a non-test database. It should refuse unless an explicit e2e marker is set (for example `STUDYAIO_E2E_SEED=1`, which the `e2e-tests` job would export), so that a mistyped `DATABASE_URL_SYNC` cannot reset a real user's password | `qa` |
| N-2 | `worker-maintenance` now runs unprivileged and writes `./backups`. Confirm the first nightly `run_backup` after the `f19efc1` deploy succeeds under that uid. A permissions failure would stop backups quietly, without losing any data | Orchestrator, `devops` (Operational dimension) |
| N-3 | `recent_negative` (admin feedback) returns an untyped `list[dict]`. A typed response model would make "no user id" structural rather than test-only | `backend` |
| N-4 | ADR 0003's `file:line` column has drifted. The `(module, function)` set is correct | `architect` |
| N-5 | The `email_sent` subject carries a file name, course code or exam title for two templates. Log the template name instead | `backend` |
| N-6 | Carried from M32 and still open: the `fastapi <0.137` cap (N-2), the `deploy.sh` key check for presence only (N-4), `pip-audit` unpinned in CI (N-5), OAuth and calendar tokens plaintext at rest (N-7), Stripe dedupe state in Redis (N-8), the empty `services/app/proof.py` (N-9). M32 N-3 is half done: `worker-maintenance` is non-root, but the two AI pools still run as root | as in M32 |

**Verdict: APPROVE**

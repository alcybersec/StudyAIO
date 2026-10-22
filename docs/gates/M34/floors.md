# M34 gate: Floors dimension

**Reviewer:** `safety` (veto role), review mode · **Date:** 2026-10-22
**Tree:** `kit/retrofit` @ `25b8538`. The gated code is `main` @ `b637dd2`, deployed to prod on 2026-10-18 by
`deploy-selfhosted` in the `main` pipeline for `b637dd2`. `git diff --stat b637dd2 25b8538` shows `docs/plan/README.md` and
`docs/risk-register.md` only. **Range:** everything after the M33 gate commit (`d06dbda`): 98 commits excluding
merges. That is SEC-005 (secrets at rest), SEC-006 option F (non-root AI pools), SEC-007 (FastAPI lift),
SEC-008 (Stripe state in Postgres), SEC-009 (M33 follow-ups), SEC-013/014 (OAuth tokens not stored, hashed
Telegram codes), SEC-015 and its follow-up (Telegram webhook secret, library log caps, settings errors),
BACKEND-012 (onboarding, case-insensitive course lookup, throttle counter), AI-010 (index embed/store split),
the M34 frontend fixes and QA-015.

Floor text is quoted from `docs/strategy.md` §6, as amended by ADR 0003, ADR 0004 and ADR 0005. The
floor-to-test map is `services/app/tests/safety/FLOORS.md`. As at M31 to M33, this file judges whether each
floor **holds in the code**, which is a stricter test than whether the tier is green. The per-change reviews it
consolidates are in this directory: `contracts-safety.md`, `sec005-safety.md`, `sec006-safety.md`,
`sec008-012-safety.md`, `sec013-014-safety.md`, `sec015-safety.md` and `fastapi-lift-safety.md`.

This review changes no `app/` code. It corrects the stale F2 `xfail` wording in one floor pin and its
`FLOORS.md` row, and adds the M34 gate delta to `docs/security/threat-model.md`.

## 1. Run evidence

### Local, on `25b8538` (the shared venv, read-only: fastapi 0.143.2)

`make test-floor`'s command. `coverage-tier.py floor` returns 95.

```
$ cd services/app && python -m pytest tests/safety -v --cov=tests/safety --cov-report=term-missing --cov-fail-under=95
TOTAL                                                    8716    193    98%
Required test coverage of 95% reached. Total coverage: 97.79%
=========== 806 passed, 1 skipped, 34 warnings in 870.78s (0:14:30) ============
EXIT=0
```

The skip is `test_floor2_setup_script_refuses_to_run_as_root`, which is `skipif(os.geteuid() != 0)`. CI runs as
root and runs it, so CI shows 807 passed and 0 skipped.

`ruff check tests/safety/` gives `All checks passed!`, and `ruff format --check tests/safety/` gives
`42 files already formatted`.

`make test` was not run, because its `bootstrap` step builds a venv in the worktree, and this review installs
nothing. The floor tier above is `make test`'s second half. CI's `backend-tests` covers the first half (below).

### Pipeline, read by job name

The jobs of the `main` pipeline for `b637dd2`, read with `glab api` (`include_retried=true`). The pipeline
is `success`, and no job is skipped, manual or retried.

| Job | Status, from the trace |
|---|---|
| `python-lint` | success |
| `backend-tests` | success: unit `Total coverage: 89.41%`, `3747 passed`; golden `317 passed`; contracts `186 passed` |
| `summary-eval` | success |
| `test-floor` | success: `Required test coverage of 95% reached. Total coverage: 97.85%`, `807 passed` |
| `integration-tests` | success: `Total coverage: 84.07%`, `686 passed` |
| `dependency-audit` | success: `No known vulnerabilities found`; `0 unallowlisted high/critical npm advisories` |
| `frontend-checks` | success |
| `e2e-tests` | success: `155 passed` |
| `build-api`, `build-ui` | success |
| `deploy-selfhosted` | success |

### Prod facts (verified by the Orchestrator after the deploy; context, not re-verified here)

- The AI pools and the maintenance pool run as uid 999.
- Every `oauth_accounts` token is NULL at head `c3e5a7b9d1f2`.
- `data/` now has a group with no members, plus setgid (R-054, closed 2026-10-18). Together with mode `750` and
  owner 999, that means only the app uid and root reach tenant files.

## 2. Mutation check (this review)

Script: `scratchpad/mutate_m34_gate.py`. It is not committed, because it edits other roles' `app/` code. It
runs on a scratch copy of the tree at `25b8538` outside the worktree, made without `.git`. It applies one mutant
at a time and runs the named pins (`pytest -x --no-cov`) before and after each one. Then it restores the file.
Every control was green before its mutants ran.

| Mutant (the fix reverted) | Pin file | Control | Mutant, first failure |
|---|---|---|---|
| **F2 at rest:** `EncryptedText.process_bind_param` returns the plaintext (`secret_box.py:196`) | `test_floor2_tokens_at_rest.py` | 41 passed | **red**: `…_credential_reaches_the_driver_as_ciphertext[calendar_syncs-access_token]` |
| **F2 MFA:** `_totp_matches` accepts an unreadable (`None`) seed (`api/auth.py:155`) | same | 41 passed | **red**: `…_unreadable_totp_seed_never_bypasses_mfa[body_extra0]` |
| **F2 OAuth:** the deploy-window `None` sweep removed (`user_service.py:804`) | same | 41 passed | **red**: `…_no_app_code_writes_a_non_none_oauth_token` |
| **F2 pairing code:** stored as plaintext (`telegram_service.py:43`) | same | 41 passed | **red**: `…_pairing_code_is_stored_and_looked_up_only_as_its_digest` |
| **F2 CLI refusal:** `ensure_claude_cli_spawnable()` removed from `_run_once` (`claude_code.py:366`) | `test_floor2_cli_shared_uid_refusal.py` | 55 passed | **red**: `…_nonroot_multi_user_refuses_before_any_login_is_read_or_spawned[setup_token-None]` |
| **F2 pools:** the worker anchor goes back to `user: "0:0"` (`docker-compose.yml:13`) | `test_floor2_worker_pools_nonroot.py` | 48 passed | **red**: `…_app_image_services_never_run_as_root[base]` |
| **F1 Stripe:** the per-customer advisory lock removed (`billing_service.py:232`) | `test_floor1_worker_jobs.py` | 11 passed | **red**: `…_webhook_ordering_is_per_customer` |
| **F1 Stripe:** a replay is not detected (`if claim_id is None` disabled) | same | 11 passed | **red**: `…_webhook_replayed_or_stale_event_mutates_nothing` |
| **F1 onboarding:** the quiz branch loses `Course.user_id == user_id` (`onboarding_service.py:136`) | `test_floor1_onboarding.py` | 13 passed | **red**: `…_onboarding_get_ignores_another_users_activity` |
| **F1 onboarding:** `PATCH` is not keyed on the caller (`onboarding_service.py:165`) | same | 13 passed | **red**: `…_onboarding_patch_writes_only_the_callers_row[dismissed]` |
| **F2 webhook:** `!=` instead of `hmac.compare_digest` (`api/notifications.py:139`) | `test_floor2_telegram_webhook_secret.py` | 25 passed | **red**: `…_webhook_secret_is_compared_only_with_compare_digest` |
| **F2 webhook:** an unset secret accepts in multi-user (`api/notifications.py:133`) | same | 25 passed | **red**: `…_unset_secret_on_a_multi_user_instance_rejects_everything[cloud]` |
| **F2 log caps:** `urllib3` uncapped (`core/logging.py:92`) | `test_floor2_library_log_levels.py` | 25 passed | **red**: `…_credential_logging_libraries_capped_at_warning` |
| **F2 log caps:** `requests_oauthlib` uncapped | same | 25 passed | **red**: same |
| **F2 log caps:** `httpx` uncapped | same | 25 passed | **red**: `…_url_logging_library_capped_at_warning[httpx]` |
| **F1 walker:** `api_routes` returns the bare `original_route` (`tests/_routes.py:28`) | `test_floor1_route_walker.py`, the non-vacuity guard | 3 passed | **red**: `…_route_walker_returns_the_effective_route` |
| **F1 walker:** `api_routes` skips the onboarding router | the non-vacuity guard | 1 passed | **red**: `test_floor1_route_enumeration_is_not_vacuous` (OpenAPI cross-check) |
| `store_artifact_chunks` deletes existing chunks when there is nothing to store (`index_service.py:258`) | `test_floor4_user_data_never_lost.py` | 22 passed | **survives the floor tier.** Red in the unit tier: `test_index_service.py::TestEmbedStoreSplit::test_store_step_with_nothing_to_store_leaves_existing_chunks` (control 40 passed) |

**No floor survivor.** The one survivor is not a floor property. Chunks are a derived search index, rebuilt
from the stored extraction. The floor-4 inventory classifies the chunk delete in `DB_SANCTIONED` on exactly that
ground (`test_floor4_user_data_never_lost.py:240`). The property is availability (Q&A on that lecture until a
re-index), and the unit tier pins it.

The per-change reviews ran a further 120 or so mutants (SEC-005 16, SEC-006 F 11, SEC-008/012 24, SEC-013/014
21, SEC-015 19 + 6, FastAPI lift 10). Every floor mutant among them was red. The only survivor was revoke on a
`None` calendar token, which is availability. This gate's re-run picks the most load-bearing of them and finds
them still red on the deployed code.

**Floor-1 sweep counts (R-040 rule).** M34 moved dependencies (FastAPI 0.136.3 to 0.143.2, plus the lock), so
the lift rule applies. I took the counts in the scratch copy through a throwaway test that calls
`_sweep_routes` and `_run_sweep`:

```
COUNTS api_routes=171 all=174 swept_pairs=135 owned_reached=113 violations=['GET /api/gamification/leaderboard'] parent_violations=[] parent_reached=113
```

| | M33 gate | M34 gate |
|---|---|---|
| `/api` APIRoutes | 169 | 171 |
| Swept method+path pairs | 133 | 135 |
| Pairs that reach an owned table | 111 | 113 |

Nothing dropped. The +2 is `GET` and `PATCH /api/onboarding`, and both are swept and reached. The counts equal
those the old walker gave on 0.136.3 (`fastapi-lift-safety.md` §2). The one violation is the ruled opt-in
leaderboard (`SWEEP_OPT_IN_CROSS_USER`).

## 3. Prior M34 `safety` verdicts rolled up

| Task | Review | Verdict | Status at the gate |
|---|---|---|---|
| S2/S3 contracts (`models.secrets-at-rest`, `models.stripe-webhook-events`, onboarding, throttle metrics, study items) | `contracts-safety.md` | APPROVE-WITH-CHANGES (C1-C7) | All of C1-C7 met in the build (`sec005-safety.md` §1). R1-R4 adopted: R1 as SEC-013, R2 and R4 in SEC-008, R3 as SEC-014 |
| M34-S2-SEC-005, secrets at rest | `sec005-safety.md` | APPROVE | Pins green; re-mutated above |
| M34-S2-SEC-006, non-root AI pools | `sec006-safety.md` | **VETO** on `b27fc19` as-is; APPROVE of option F with the §5 pins | The veto is discharged: option F landed (`759ff94`, `93dcaca`, `f3a43d4`) with the pins (`aa9fbdb`). Re-mutated above |
| M34-S2-SEC-007, FastAPI lift | `fastapi-lift-safety.md` | APPROVE | Walker pin and OpenAPI cross-check green; re-mutated above |
| M34-S2-SEC-008, M34-S3-BACKEND-012 | `sec008-012-safety.md` | APPROVE | Green; re-mutated above |
| M34-S2-SEC-013, SEC-014 | `sec013-014-safety.md` | APPROVE | Green; re-mutated above. Prod: OAuth tokens all NULL |
| M34-S2-SEC-015 and its follow-up | `sec015-safety.md` §1-§7 | APPROVE, APPROVE | F1 (`9e5e4f7`) and F2 (`5e1eda8`) are fixed; both strict `xfail`s are now plain tests. Re-mutated above |

**No `safety` VETO is open.** The backend tests contain no `xfail` marker, and e2e contains no `test.skip`,
`fixme` or `fail` (`grep -rn "xfail" services/app --include=*.py`,
`grep -rnE "test\.(skip|fixme|fail)\(" services/ui/e2e`). The only match was the docstring of
`test_floor2_library_log_levels.py`, which still called F2 a strict `xfail` after `backend` removed the marker
in `5e1eda8`. This review corrects that docstring and the `FLOORS.md` row (§5).

## 4. Per-floor judgement

### Floor 1: tenant isolation

> an authenticated endpoint never returns or mutates another user's rows; every user-owned query filters on user_id

**Holds in the code: YES.**
- **Route sweep after the lift.** Since SEC-007 the guards walk the effective route of each lazy include
  (`tests/_routes.py:26`, `fastapi.routing.iter_route_contexts`). An OpenAPI cross-check fails if the walker
  misses any documented operation (`test_floor1_tenant_isolation.py:167`). An include-level dependency reaches
  `_requires_user` (`test_floor1_route_walker.py:56`, `:78`). The counts (§2) are whole, and both walker
  mutants are red.
- **Onboarding (BACKEND-012).** Every read binds the caller. The `quiz_attempts` branch is scoped through
  `courses.user_id`, and `PATCH` is keyed on `users.id == caller` with `extra="forbid"`
  (`test_floor1_onboarding.py:148`, `:226`). Both re-mutated red.
- **Stripe webhook (SEC-008).** The mutation is keyed on the signed event's customer only. The claim and the
  effect share one transaction, ordering runs under a per-customer advisory lock, and a replay mutates nothing
  (`test_floor1_worker_jobs.py:339`, `:365`). Account deletion nulls the deleted user's customer id with an
  `UPDATE`, never a `DELETE` (`:422`, `:478`). `stripe_webhook_events` is classified unowned (no `user_id`, and
  no route reads it). Re-mutated red.
- **Course lookup on card and quiz add.** `get_course_by_code_ci` takes a required `user_id` and never creates a
  course. The M33 study-item pins stay green.
- **Telegram webhook (SEC-015).** A forged update is refused before any statement runs. An authentic one can
  pair only the row whose digest matches its code. `verify_link` stays in `UNSCOPED_FUNCTION_ALLOWED` with that
  reason.
- Still open, not red: R-010. `review_items` and `quiz_attempts` have no `user_id` and are scoped by join.
  Carried since M31 (§6).

### Floor 2: no secrets in the tree

> no plaintext credentials, tokens or keys committed, and per-user AI credentials are never logged or returned by the API

**Holds in the code: YES.**
- **Committed files.** The tracked-file scan ran with git present, locally and in CI. M34 committed no
  credential. The new settings (`TELEGRAM_WEBHOOK_SECRET`, `TELEGRAM_BOT_USERNAME`,
  `CLAUDE_CLI_SHARED_UID_ACCEPTED`) appear in `.env.example` only as commented placeholders.
- **Per-user AI credentials.** Their encryption at rest, the never-echoed GET/PUT/export and adapter-boundary
  redaction are unchanged and green. New: the OpenAI and Anthropic adapters never log a per-user key at `DEBUG`,
  on a 200 or a 401. Each pin asserts that the key reached the transport, so it cannot pass vacuously
  (`test_floor2_library_log_levels.py`). The Claude Code availability surface (`f3a43d4`) returns a
  secret-free reason and spawns nothing.
- **Secrets at rest (SEC-005, SEC-013, SEC-014).** Calendar tokens and the TOTP seed bind as `enc:v1:`
  ciphertext (`test_floor2_tokens_at_rest.py:130`). An unreadable seed never disables or bypasses MFA (`:198`).
  Rotation works on stored strings and never rewrites an unreadable value (`:313`). Every downgrade abort
  changes nothing (`:596`). No app code writes a non-`None` OAuth token (`:650`). Pairing codes are stored and
  looked up as SHA-256 digests only (`:913`). Both engines set `hide_parameters=True`, and the logging backstop
  no longer over-redacts JSON lines (`277b72a`).
- **Logs.** `configure_logging` caps nine URL- or credential-logging libraries at `WARNING` whatever
  `LOG_LEVEL` says (`core/logging.py:92`). A `Settings` validation error never echoes a `SecretStr` value
  (`hide_input_in_errors`). Stripe customer ids are logged as a fingerprint (`277b72a`). `email_sent` names the
  template, not the subject (`3291b1f`, M33 N-5). The Q&A log no longer carries the question (`3291b1f`).
- **Worker pools and the CLI (SEC-006 F).** Every app-image service runs non-root in every stack
  (`test_floor2_worker_pools_nonroot.py:181`), and the Dockerfile pins `studyaio` to 999:999
  (`services/app/Dockerfile:90`). On a non-root multi-user worker the adapter refuses the CLI before it reads
  any login or spawns (`test_floor2_cli_shared_uid_refusal.py:184`). The opt-in is never defaulted on. Prod
  pools run as 999 (Orchestrator). The residual is the threat model's B4: with the opt-in, the child shares the
  worker's uid.
- **Telegram (SEC-015).** The webhook secret is compared once with `hmac.compare_digest`
  (`test_floor2_telegram_webhook_secret.py:216`), fails closed when unset on multi-user (`:335`), and is never
  returned, logged or printed by the CLI.

### Floor 3: AI only via the adapter (ADR 0003, ADR 0005)

**Holds in the code: YES.**
- The request-time `get_agent` sites are still the five in ADR 0003: `api/qa.ask_question` (`qa.py:110`),
  `api/settings.test_ai_connection` (`settings.py:117`), `chat_service.send_message` (`:480`),
  `chat_service.stream_message` (`:646`) and `concept_service.extract_and_save_concepts` (`:112`). The
  worker-side sites are the five Celery task modules. M34 added no `get_agent` caller
  (`test_floor3_ai_via_adapter.py:460`, `:496`).
- **AI-010 (index embed/store split).** `aembed_artifact_chunks` is the embedding call, and
  `store_artifact_chunks` never calls a provider. ADR 0005 was amended (`8c25495`) for the new
  `(module, function)` pair before the pins moved (`1766c17`, `8251b05`).
- **SEC-006 F.** The `test-ai` 422 for an unavailable `claude_code` answers from
  `claude_code_availability()`, before `get_agent` (`settings.py:103`). It adds no site.
- ADR 0003's `file:line` column was refreshed in `110f84b` (M33 N-4), but it has drifted again: `f3a43d4`
  moved `settings.py:111` to `:117`. The pin compares `(module, function)` pairs, so it is unaffected (§6, N-3).

### Floor 4: user data is never lost (ADR 0004)

**Holds in the code: YES.**
- **No new delete of uploads or generated content.** The floor-4 delete inventory is exact and green. The
  chunk delete in `store_artifact_chunks` is classified (derived index). Since AI-010 it runs only after the
  vectors exist, and only when there is something to store (the unit tier pins the empty case, §2).
- **Revision `c3e5a7b9d1f2`** nulls OAuth tokens and pending pairing codes with Core `UPDATE`s. It deletes no
  row and keeps every linked chat. Its downgrade restores no token and nulls every digest
  (`test_floor2_tokens_at_rest.py:1131`). Those are credentials, not user content.
- **Revision `b2d4f6a8c0e1` (SEC-005).** The upgrade aborts on multi-user with no key. The downgrade aborts,
  changing nothing, on no key, an undecryptable value or a value that is too long. These paths were run live
  against Postgres in `sec005-safety.md` §4, and are pinned.
- **Stripe event rows** are kept indefinitely (ruling 3). Account deletion unlinks them and never deletes them.
  A failed effect releases its claim, so Stripe's retry applies (`test_floor1_worker_jobs.py:390`).
- **Account deletion** is still the only path that removes `data/` content. The new `users` column
  (`onboarding_checklist`) goes with the user row.
- Prod `data/` now has a group with no members (R-054). That is an access change, and it deletes nothing.

## 5. Changes made in this review (`safety` paths only)

- `services/app/tests/safety/test_floor2_library_log_levels.py`: the module docstring no longer calls F2 a
  strict `xfail` or "RED until", and records the fix commit. `F2_UNCAPPED` is renamed `F2_CAPPED`. No assertion
  changed.
- `services/app/tests/safety/FLOORS.md`: the F2 row and the mutation note now describe a plain test.
- `docs/security/threat-model.md`: B2, B4, B5, B9 and B10 are updated for what M34 landed, and §5 gains the
  "2026-10-22, M34 gate" delta.

## 6. Carry-over tally

### Notes from M32 and M33

| Note | Raised | Owner | M34 outcome |
|---|---|---|---|
| M33 N-1: `seed_e2e.py` guard | M33 | `qa` | **Closed** `f60b9ea`: refuses without `STUDYAIO_E2E_SEED=1` and a local DB host |
| M33 N-2: first non-root nightly backup | M33 | Orchestrator | **Closed** M34-OPS-003, 2026-10-16 |
| M33 N-3: `recent_negative` untyped | M33 | `backend` | **Closed** `3291b1f`, typed response |
| M33 N-4: ADR 0003 `file:line` drift | M33 | `architect` | **Closed** `110f84b`, **but recurred** (`settings.py:111` is now `:117`), see N-3 below |
| M33 N-5: `email_sent` logs the subject | M33 | `backend` | **Closed** `3291b1f`, template only |
| M32 N-2: `fastapi <0.137` cap | M32 | `safety`, `devops` | **Closed** `3fbebef`, `e7d6e1e` |
| M32 N-3: AI pools run as root | M32 | `devops`, `ai` | **Closed** by SEC-006 F (prod uid 999). Isolation became refusal, and option B (the CLI sidecar) is in the backlog (`docs/strategy.md:308`) |
| M32 N-4: `deploy.sh` key check presence-only | M32 | `devops` | **Closed** `8c64d1c`: it runs `secret_box.check_startup()` (`infra/deploy/deploy.sh:197`) |
| M32 N-5: `pip-audit` unpinned | M32 | `devops` | **Closed** `8c64d1c` (`pip-audit==2.10.1`) |
| M32 N-7: OAuth and calendar tokens plaintext | M32 | `backend`, `data` | **Closed** by SEC-005 and SEC-013. Prod OAuth tokens are NULL |
| M32 N-8: Stripe dedupe in Redis | M32 | `backend`, `data` | **Closed** by SEC-008 |
| M32 N-9: empty `proof.py` | M32 | `backend` | **Closed** `3291b1f` |
| M33 §6: every pool gets `.env` | M33 | `devops` | Open. Under F, a CLI child at the worker's uid could read it (B4). Option B removes the need |
| M33 §6: targeted-prompt delimiters not escaped | M33 | `ai` | Open. Self-only reach |
| M33 §6: daily cap is count-then-insert | M33 | `backend` | Open. One extra generation per race; quota bounds spend |

### Older risks that have now survived two milestones or more (flagged)

| Risk | Open since | Floor | Why it is not red | Ask |
|---|---|---|---|---|
| **R-010**: `review_items` and `quiz_attempts` carry no `user_id`, scoped by join | M31 | 1 (literal text) | Every route that reads them joins to an owned parent, and the sweep classifies both as owned. M34's onboarding quiz branch is pinned on `courses.user_id` | `data`: add `user_id`, or have the Orchestrator rule a permanent exception in the floor text. Four milestones is long enough to decide |
| **R-009**: no portable secret scanning in CI; the `.secrets.baseline` is unaudited | M31 | 2 | The floor tier's own tracked-file scan runs in CI with git present (R-018 fixed) | `devops`: detect-secrets in CI, or close R-009 as superseded by the floor scan |
| **R-020**: the row still lists the empty-ledger sweep and S3 `list_keys` as open | M31 | 4 (adjacent; an erasure gap, not loss) | Both were fixed in M32-S1-BACKEND-006. `test_floor4_account_purge_ignores_ledger_entries_that_name_no_course` is green. The row text is stale | Orchestrator: update the row. Only the pre-`a3ab6ce` residual remains |
| **R-012**: worker-side provider errors | M31 | 2 | Fixed, and the pins are green at this gate (`test_floor2_no_secrets.py`, worker provider-error sweep). The row says "closes on `safety` gate re-review" | This review is that re-review: **close R-012** |

### Raised in M34 and still open (one milestone)

| # | Note | Owner |
|---|---|---|
| N-1 | R-048: Telegram pairing codes never expire | `backend`, `data` |
| N-2 | SEC-006 option B (the CLI sidecar) is in the backlog. Until it lands, `CLAUDE_CLI_SHARED_UID_ACCEPTED` or single-user mode runs the child at the worker's uid (B4) | `architect` (ADR), then `ai` and `devops` |
| N-3 | The ADR 0003 `file:line` column drifts with every edit near a site (twice now). Drop the line column or mark it informative. The `(module, function)` set is correct | `architect` |
| N-4 | `test_no_response_model_carries_a_token_field` (contracts) has no non-vacuity floor of its own (`fastapi-lift-safety.md` §6.1) | `architect` |
| N-5 | The `TelegramLink` model docstring does not say the column holds a digest (`sec013-014-safety.md` §5.3) | `data` |
| N-6 | `models.secrets-at-rest v3` must drop the two `oauth_accounts` token columns together with their `RAW_SECRET_COLUMNS` and `MUST_ENCRYPT` entries. It can land in the release after M34, since prod has served on `c3e5a7b9d1f2` since 2026-10-18 and the one-release window has passed | `data`, `backend`, then `safety` re-pins |
| N-7 | Recommended, not required: the one-time unset-secret warning also in single-user mode (`sec015-safety.md` §3) | `backend` |

None of these is a floor defect.

## 7. Threat-model delta (M34)

The full text is in `docs/security/threat-model.md` §5, under "2026-10-22, M34 gate", after the five per-change
deltas written during the milestone. The boundary rows B2, B4, B5, B9 and B10 now describe the code as deployed.
Summary:

| Surface | Judgement | Residual |
|---|---|---|
| Secrets at rest (SEC-005) | Calendar tokens and the TOTP seed are `enc:v1:`. Fails closed when unreadable. Raw-string rotation and migration | The key sits in the same `.env` as the DB password; the downgrade removes protection (operator-only) |
| OAuth sign-in tokens (SEC-013) | Not stored; NULL on prod | Issued tokens stay valid at the provider until expiry |
| Telegram pairing and webhook (SEC-014, SEC-015) | Digest at rest and in the lookup; dedicated secret, constant-time compare, fail closed | Codes never expire (R-048) |
| Non-root AI pools (SEC-006 F) | Parsers run at uid 999. The CLI is refused rather than isolated, and the availability is reported in settings | Opt-in or single-user shares the worker's uid (option B pending) |
| Route guards after the FastAPI lift (SEC-007) | Effective routes, OpenAPI cross-check, include-level dependency pin | Hidden routes rely on the authn guard's exact public allowlist |
| Stripe state in Postgres (SEC-008) | Atomic claim and effect, per-customer lock, unlink on deletion | Events in the same second are not ordered |
| Onboarding (BACKEND-012) | Caller-scoped reads and write | none |
| Library logging and settings errors (SEC-015 follow-up) | Nine libraries capped whatever `LOG_LEVEL` says; no `SecretStr` echoed | A future validator that interpolates a secret into its own message would bypass `hide_input_in_errors` |
| Index embed/store split (AI-010) | Embed first, then replace in one transaction; nothing stored means nothing deleted | none |

**Verdict: APPROVE**

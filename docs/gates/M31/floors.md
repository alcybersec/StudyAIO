# M31 gate — Floors dimension

**Reviewer:** `safety` (veto role), review mode · **Date:** 2026-10-04 · **Tree:** `kit/retrofit` @ `2da6f17`
(GitLab pipeline on that sha: `status: success`, job `test-floor: success`, read by job name.)

Floor text is quoted from `docs/strategy.md` §6 as amended by ADR 0003. The floor-to-test map lives in
`services/app/tests/safety/FLOORS.md`. This file judges whether each floor **holds in the code**. That
is a stricter question than whether the floor tier is green.

## Run evidence

```
$ cd services/app && .venv/bin/python -m pytest tests/safety -q -rxX
XFAIL test_floor1_tenant_isolation.py::test_floor1_no_cross_user_route_awaits_a_ruling
XFAIL test_floor4_user_data_never_lost.py::test_floor4_no_delete_site_awaits_a_ruling
XFAIL test_floor4_user_data_never_lost.py::test_floor4_resummarize_preserves_prior_version
XFAIL test_floor4_user_data_never_lost.py::test_floor4_asset_regeneration_keeps_study_history
33 passed, 4 xfailed, 6 warnings in 32.20s
```

```
$ make test-floor
# pytest tests/safety -v --cov=tests/safety --cov-fail-under=<floor tier from pyproject>
TOTAL                                                928     32    97%
Required test coverage of 95% reached. Total coverage: 96.55%
============= 33 passed, 4 xfailed, 6 warnings in 73.40s (0:01:13) =============
EXIT=0
```

**§11 gate addition.** It requires that "the floor tier must be non-empty and green, and every floor in §6 must map to
a named test." **Met.** The tier has 37 tests, with 0 failed and 0 XPASS, and each of floors 1–4 maps to named tests
below. The four xfails are `strict=True`, and each one is a floor question waiting on the user's ruling. They are not
passes (`FLOORS.md`).

Meeting the gate addition is necessary but not sufficient. Floors 1 and 2 have live violations that the tier does not
see (below). That is why the verdict is a VETO even though the tier is green.

---

## Floor 1 — tenant isolation

> an authenticated endpoint never returns or mutates another user's rows; every user-owned query filters on user_id

**Named tests** (`services/app/tests/safety/test_floor1_tenant_isolation.py`):
- `test_floor1_route_sweep_every_owned_query_filters_on_caller`
- `test_floor1_every_table_is_classified`
- `test_floor1_no_unscoped_session_get_on_owned_model`
- `test_floor1_pipeline_only_fetch_is_pipeline_only`
- `test_floor1_cannot_attach_document_to_another_users_assessment` (V1 regression pin)
- `test_floor1_no_cross_user_route_awaits_a_ruling`: strict xfail, waiting on the leaderboard ruling

**Run:** 5 passed, 1 xfailed.

**Closed in M31:** V1 (`attach_assessment_document` cross-tenant attach) was fixed in BACKEND-008 (`a2cd687`). `safety`
approved it in SAFETY-009, and the pin was mutation-checked.

**Open: live violations (R-015), found by QA-007 and not caught by this tier.** Each one is a strict xfail in
`services/app/tests/integration/`, run against real Postgres:

| Finding | Pinned by (integration tier) |
|---|---|
| `POST /study/review`: flashcard looked up without an owner filter; SM-2 row written for it | `test_api_study_exams.py::test_cannot_review_another_users_flashcard` |
| `POST /study/quiz-attempt`: question/exam never checked against the caller | `test_api_study_exams.py::test_cannot_attempt_another_users_quiz_question` |
| `POST /study/timed-plan`: `generate_timed_plan` takes no `user_id`, so it returns other users' card/quiz ids | `test_api_study_exams.py::test_timed_plan_contains_only_callers_ids` |
| `POST /qa/ask`: `course_code` resolved unscoped (existence oracle; 500 when two users share a code) | `test_api_content_reads.py::test_course_code_of_another_user_is_404`, `::test_shared_course_code_between_users_still_answers` |
| `GET /courses/{code}/weeks/{n}`: summary matched on code only | `test_api_courses_files.py::test_week_detail_never_returns_another_users_summary` |
| `pipeline/classify._get_known_courses` sends every user's course codes to the AI provider | `test_pipeline_end_to_end.py::test_classify_does_not_leak_other_users_course_codes` |
| `achievement_service.mark_notified` unscoped | `test_gamification.py::test_cannot_mark_another_users_achievements_notified` |

**Why the floor-1 sweep missed them (my own gap).** I found this by reading the harness:
1. The sweep sends `json={}` to every POST/PUT/PATCH route. Any route whose foreign id arrives in the **request body**
   (`/study/review`, `/study/quiz-attempt`, `/study/timed-plan`, `/qa/ask`) fails Pydantic validation with a 422, so
   the handler never runs and no SQL is captured.
2. The sweep puts the same string foreign id into every path parameter. A **typed** path parameter (for example, the
   `int` in `/courses/{course_code}/weeks/{week}`) also fails with a 422 before the handler.
3. The sweep covers routes only. Unscoped **service or pipeline functions** (`_get_known_courses`, `mark_notified`)
   need a function-level check.

The floor of 60 routes reached (74 today) did not expose this, because the routes it reaches are mostly path-id
routes. The sweep is therefore sound for what it reaches, but it does not cover body-borne ids.

**Open ruling:** the leaderboard (`xp_service.get_leaderboard`) returns other users' id, username and XP with no
opt-in. This is held as a strict xfail.

**Related, not red:** R-010. `review_items` and `quiz_attempts` have no `user_id` column. The sweep classifies them
as owned through the FK closure, so a join-scoped query must still carry a `user_id` comparison.

**Status: RED.** Seven live cross-tenant read/write paths remain, plus one open ruling.

---

## Floor 2 — no secrets in the tree

> no plaintext credentials, tokens or keys committed, and per-user AI credentials are never logged or returned by the API

**Named tests** (`services/app/tests/safety/test_floor2_no_secrets.py`):
- `test_floor2_settings_get_never_returns_a_stored_credential`
- `test_floor2_settings_put_never_echoes_a_credential`
- `test_floor2_settings_schemas_carry_no_credential_value`
- `test_floor2_account_export_never_returns_a_stored_credential` (V2 regression pin)
- `test_floor2_provider_error_never_echoes_a_stored_credential[...]`, run once for each of: `POST /api/settings/test-ai`, `POST /api/qa/ask`, `chat_service.send_message`, `chat_service.stream_message`
- `test_floor2_credentials_never_logged`
- `test_floor2_no_high_confidence_secret_in_tracked_files`
- `test_floor2_no_env_file_tracked`
- `test_floor2_detect_secrets_baseline_is_wired_and_clean`
- `test_floor2_sentinels_are_not_secret_shaped`

**Run:** all passed.

**Closed in M31:**
- V2: the account export returned plaintext AI keys. Fixed in `b5f57e6` and approved in SAFETY-009.
- R-008 at `test-ai`: fixed in `7eecbac`.

**BACKEND-010 (R-008 at `qa/ask` and chat): CONFIRMED.** I reviewed the diff `65adbfc..718faa0`:
- `settings_service.redacted_error` wraps `redact_user_secrets`. That scrubs every string leaf of each `SECRET_KEYS`
  value, including the nested CLI token, and also scrubs the instance's own provider keys, longest match first. If the
  scrub itself fails, the error text is withheld.
- `api/qa.py` logs and returns only the redacted text, and uses `from None`, so the original exception does not ride
  along as the cause.
- All four `chat_service` log lines are redacted: the RAG and agent errors in both send and stream. The streamed
  client message is generic.

**Mutation check.** I worked in a scratch copy of `services/app` and reverted the redaction to `str(e)` at two of the
four call sites: the `qa_agent_error` log and the `chat_stream_error` log. The result was
`2 failed, 2 passed`, and the two failures were exactly the mutated sites. The pin discriminates and does not pass
vacuously. R-008 is closed for the four sites the test covers.

**Open: new violation found in this review (latent, unpinned).** ADR 0003 site #5, `POST /api/concepts/extract/{artifact_id}`:
- Adapters raise `AgentError(f"... API call failed: {e}")`, which carries the SDK text verbatim (`agents/anthropic_api.py`,
  `openai_adapter.py`, `ollama_adapter.py`; `claude_code.py` carries CLI stderr).
- `concept_service.extract_and_save_concepts` does not catch it.
- `AgentError` is a `StudyAIOError`, so it reaches `main.py`'s global `studyaio_error_handler`. That handler **both logs
  `error=str(exc)` and returns `{"detail": str(exc)}`**.

**Demonstrated end to end.** A scratch script drove the real app through `httpx.ASGITransport`, with an adapter raising
an `AgentError` that quotes a sentinel credential. Output:

```
adapter called: 1
status: 500
sentinel in response: True
sentinel in structlog: True
events: ['unhandled_studyaio_error', 'http_request']
```

This is the same leak class as R-008, with the same precondition: a provider echoes the key in its error text. My own
floor-2 test missed it. Its `REQUEST_TIME_AI_ERROR_SITES` excludes the concepts site on the assumption that the failure
"propagates unhandled to a generic 500". The code above shows that assumption is false. The global handler also echoes
`str(exc)` for **every** `StudyAIOError`, which is a wide surface for information disclosure.

**Open: R-012 (worker side, unpinned).** `*_task_error` logs and `pipeline_runs.error_message` carry adapter error
text that has not been redacted. The fix at the adapter boundary (below) closes it together with site #5.

**Open, outside the literal floor (threat model only):**
- R-009: no portable secrets scanning in CI. The floor tier's high-confidence scan runs in the `test-floor` job, which
  partly mitigates this, but the 50 baseline entries are still unaudited.
- R-017: OAuth and calendar tokens are stored in plaintext at rest. They are not "per-user AI credentials" and not
  committed.

**Doc drift (mine):** `tests/safety/FLOORS.md` still says the provider-error test is "RED today" at qa/chat. That has
been stale since `718faa0`. I will fix it in the follow-up task below, not in this review.

**Status: RED.** Site #5 echoes a credential in the response and the log.

---

## Floor 3 — AI only via the adapter (ADR 0003)

> every AI call goes through AgentAdapter, obtained via `get_agent`; `get_agent` is called only in `app/pipeline/**`
> (the Celery worker) and at the request-time call sites enumerated in ADR 0003, and a new request-time call site
> requires amending that ADR

**Named tests** (`services/app/tests/safety/test_floor3_ai_via_adapter.py`). These are ADR 0003's three checks, plus a
non-vacuity check:
- `test_floor3_request_time_get_agent_sites_equal_adr_0003_allowlist`
- `test_floor3_no_provider_sdk_import_outside_agents`
- `test_floor3_no_adapter_class_reference_outside_agents`
- `test_floor3_no_claude_cli_spawn_outside_agents`
- `test_floor3_pipeline_get_agent_only_in_celery_task_modules`
- `test_floor3_detectors_are_not_vacuous`

**Run:** all passed. The request-time set equals the five-entry allowlist exactly.

**Closed in M31:** R-001. The second clause was already violated at adoption. It was amended by ADR 0003 with the
user's agreement, which is a recorded weakening, and is now pinned exactly.

**Open ruling: R-004, embeddings.** `EmbeddingProvider` (`agents/embeddings.py`) is a second remote-model path. It runs
at request time (`api/qa.py`, `chat_service` send and stream, `concept_service`) and in `pipeline/index.py`.
- The backend is instance-wide by design, not per user, so it does not touch per-user credentials.
- Floor 3 never defined "AI call", so these calls are neither inside nor outside the floor. The tier deliberately does
  not cover them.
- `FLOORS.md` §3 lists the test that would land on either ruling.

I cannot certify a floor whose scope is undefined.

**Status: GREEN as tested; scope OPEN** pending the R-004 ruling.

---

## Floor 4 — user data is never lost

> nothing deletes uploads or generated content under data/ except explicit account deletion, and dedup/re-summarize
> never destroys prior versions

**Named tests** (`services/app/tests/safety/test_floor4_user_data_never_lost.py`):
- `test_floor4_every_blob_delete_is_classified`
- `test_floor4_every_content_row_delete_is_classified`
- `test_floor4_account_purge_reachable_only_from_account_deletion`
- `test_floor4_lecture_upload_dedup_writes_and_deletes_nothing`
- `test_floor4_reference_checked_delete_has_only_classified_callers`
- `test_floor4_duplicate_course_document_upload_keeps_original_blob` (V3 regression pin)
- `test_floor4_failed_assessment_attach_keeps_existing_blob` (V4 regression pin)
- `test_floor4_failed_upload_never_deletes_another_users_blob`
- `test_floor4_resummarize_increments_version`
- `test_floor4_resummarize_preserves_prior_version`: strict xfail, waiting on a ruling
- `test_floor4_asset_regeneration_keeps_study_history`: strict xfail, waiting on a ruling
- `test_floor4_no_delete_site_awaits_a_ruling`: strict xfail, waiting on a ruling

**Run:** 9 passed, 3 xfailed.

**Closed in M31:** V3 and V4. The courseops upload failure paths used to delete blobs that were still referenced.
Fixed in `a2cd687` with a reference-checked, prefix-scoped discard, and approved in SAFETY-009.

**Open rulings (R-007). The shipped behaviour matches the PRD, and the floor text forbids it:**
1. Re-summarize overwrites `summaries.content_md` and the `Week<N>.md` blob in place, so version N-1 is gone.
   QA-007 also pins this at the integration tier:
   `test_pipeline_end_to_end.py::test_resummarize_retains_prior_version_content`.
2. Asset regeneration deletes flashcards and quiz questions. The cascade then removes `flashcard_reviews` and
   `quiz_attempts`, which is the user's study history.
3. Single-item user deletes are not "account deletion". These are course, course document, deadline, chat session and
   merge-discard.

(The fourth R-007 ruling, the leaderboard, is under floor 1.)

**Open, adjacent:**
- R-013: a race between concurrent same-bytes uploads where one fails. The pre-fix code was strictly worse, and nothing
  is disclosed. Low.
- R-016: `delete_user_account` hits an FK violation for any user who has a course document or assessment
  (`test_account_deletion_courseops.py`, strict xfail). The floor's **only sanctioned** deletion path is broken. That
  loses no data, but it fails the user's right to erasure. Not floor-red; it is a GDPR-relevant defect.

**Status: GREEN as tested; 3 strict-xfail rulings OPEN.**

---

## Threat-model delta for M31

**What changed**
- **Floor 3 weakened by ADR 0003.** Five named request-time `get_agent` sites now run on the API event loop. The only
  back-pressure is the per-route rate limits and `quota_service.check_ai_quota`. The ADR accepts this rather than
  solving it. Every request-time AI failure path is now an exposure surface for credential echo in API responses.
  Before, it only reached worker logs.
- **Floor tier introduced and enforced.** It is `services/app/tests/safety/` (37 tests, guard coverage 96.55%), wired
  into `make test` and the `test-floor` CI job. CI now blocks committed high-confidence secret formats and tracked
  `.env` files.
- **Coverage measurement corrected.** R-017's greenlet concurrency fix means async handler bodies are now measured.
  Integration coverage figures are trustworthy as evidence.
- **Redaction primitive added.** `settings_service.redact_user_secrets` and `redacted_error` cover per-user and
  instance credentials, including JSON-nested values. This is the right building block, but it is applied
  call site by call site instead of once at the adapter boundary.

**What closed**
- V1: cross-tenant attach (F1).
- V2: plaintext AI keys in the account export (F2).
- V3 and V4: referenced blobs deleted on upload failure (F4).
- R-008: provider error echo at `test-ai`, `qa/ask`, and chat send and stream (F2).
- R-001: superseded by ADR 0003.

**New exposures found during M31**
- **F2, this review:** `POST /api/concepts/extract/{id}` returns and logs adapter error text unredacted, through the
  global `StudyAIOError` handler. That handler echoes `str(exc)` for every application error, so it is a general
  information-disclosure path.
- **F2, R-012:** worker task logs and `pipeline_runs.error_message` carry adapter error text that has not been redacted.
- **F1, R-015:** seven unscoped read/write paths. The floor-1 sweep misses body-borne ids, typed path parameters and
  non-route functions.
- **Cross-tenant disclosure to a third party:** `classify._get_known_courses` sends every user's course codes to the
  AI provider inside the prompt.
- **Other (R-017):** the Telegram webhook accepts any caller when `telegram_webhook_url` is empty, and OAuth and
  calendar tokens are stored in plaintext. Both still need `safety` triage.
- **Process (R-011):** the ownership guard does not fence isolated worktrees. Diffs have been checked by hand: clean
  for ARCH-006, SAFETY-003, BACKEND-008 and BACKEND-010.

---

Verdict: VETO

**What lifts the VETO** (each item needs evidence: a green test that was first shown red, and `safety` re-review):

1. **Floor 1, R-015.** Scope the seven findings listed under floor 1, so that their strict xfails in
   `tests/integration` turn XPASS and the markers come off.
   **Owner:** `backend` (study review, quiz-attempt and timed-plan, qa course lookup, week detail, `mark_notified`);
   `ai` (`classify._get_known_courses`).
2. **Floor 1, sweep gap.** Extend the floor-1 sweep to cover body-borne ids and typed path parameters: build each body
   from its schema with foreign ids in it, and use a type-valid foreign value for each path parameter. Add a
   function-level scoping check for service and pipeline functions that take an id and no `user_id`. Show each new check
   red on the R-015 code before the fixes land.
   **Owner:** `safety`.
3. **Floor 2, concepts site #5 and R-012.** Redact credential values at the adapter boundary, at `AgentError`
   construction in `app/agents/**`, so that both processes and every call site are covered.
   **Owner:** `ai`.
   Separately, stop `studyaio_error_handler` from echoing `str(exc)` for `AgentError` (return a generic detail and log
   the redacted text).
   **Owner:** `backend`.
   `safety` adds `POST /api/concepts/extract/{id}` to `REQUEST_TIME_AI_ERROR_SITES` and adds a worker-side pin on
   `pipeline_runs.error_message` and task logs, then corrects the stale `FLOORS.md` line.
   **Owner:** `safety`.
4. **Floor 4 and floor 1, R-007.** The user rules on each of the four strict xfails (leaderboard, re-summarize
   overwrite, regeneration cascade, single-item deletes). Each ruling is either "fix the code" or "amend the floor".
   **Owner:** user.
   Then, depending on the ruling: if fixed, `backend` and `ai` change the code; if amended, `architect` writes the ADR.
   `safety` removes the matching `*_PENDING_RULING` entries and xfail markers.
5. **Floor 3, R-004.** The user and `safety` rule on whether embeddings are AI calls.
   **Owner:** user.
   If they are, `architect` amends ADR 0003 to name `get_embedding_provider` and its allowlist. In either case,
   `safety` lands the matching pin described in `FLOORS.md` §3.

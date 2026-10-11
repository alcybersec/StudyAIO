# M31 gate re-run: Floors dimension

**Reviewer:** `safety` (veto role), review mode · **Date:** 2026-10-08
**Tree:** `kit/retrofit` @ `82f29c8`. The gated code sha is `8d9de14`; `82f29c8` changes only `docs/plan/README.md`
(`git diff --stat 8d9de14 82f29c8` shows 1 file).
**Supersedes the verdict in** `docs/gates/M31/floors.md` (2026-10-04, VETO). That file is left as written.

Floor text is quoted from `docs/strategy.md` §6 as amended by ADR 0003, ADR 0004 (including its amendment and
clarification) and ADR 0005. The floor-to-test map is `services/app/tests/safety/FLOORS.md`. As in the first run, this
file judges whether each floor **holds in the code**, which is a stricter question than whether the tier is green.

## Run evidence

**Local, on this tree (`make test-floor`'s command, run with the main checkout's venv because the worktree has none):**

```
$ cd services/app && python -m pytest tests/safety -v --cov=tests/safety --cov-report=term-missing \
    --cov-fail-under=$(python ../../scripts/coverage-tier.py floor)
TOTAL                                               2049     55    97%
Required test coverage of 95% reached. Total coverage: 97.32%
================== 72 passed, 6 warnings in 88.45s (0:01:28) ===================
EXIT=0
```

**Pipeline, read by job name (`glab api projects/:id/pipelines/<id>/jobs`):** the pipeline on `8d9de14`, ref
`kit/retrofit`, status `success`. Jobs: `test-floor`, `backend-tests`, `integration-tests`, `e2e-tests`,
`frontend-checks` and `python-lint` all report `success`. The `test-floor` trace ends with
`Required test coverage of 95% reached. Total coverage: 97.32%` and `72 passed, 6 warnings in 164.10s`.

**§11 gate addition** ("the floor tier must be non-empty and green, and every floor in §6 must map to a named test"):
**met.** The tier has 72 tests, with 0 failed, 0 xfail and 0 XPASS. No `xfail` marker remains under `tests/safety`, and
each floor maps to named tests in `FLOORS.md`.

### Independent mutation check (this review)

A green tier only matters if it can go red. So I reverted each VETO-lift fix, one at a time, in a scratch copy of
`services/app` taken from this tree, and ran the matching floor test file. The script is
`scratchpad/mutate_rerun.py`. It was not committed, because it applies edits to `app/` code that belongs to other
roles. On the scratch copy, the git-dependent committed-file scans in floor 2 are deselected, since the copy has no
`.git`.

| # | Mutation (the fix reverted) | Floor test that went red |
|---|---|---|
| 1a | `GET /courses/{code}/weeks/{n}` calls `get_summary_for_week` without `user_id` | `test_floor1_route_sweep_owned_parent_never_unlocks_foreign_rows` |
| 1b | `mark-notified` route drops `user_id` | `…every_owned_query_filters_on_caller`, `…owned_parent_never_unlocks_foreign_rows` |
| 1c | `timed-plan` route drops `user_id` | same two |
| 1d | `qa/ask` resolves `course_code` with an unscoped `select(Course)` | same two |
| 1e | `study/review` looks the flashcard up unscoped | same two |
| 1f | `study/quiz-attempt` looks the question up unscoped | same two |
| 1g | `classify._get_known_courses` without `Course.user_id` | `test_floor1_no_unscoped_query_function_outside_classification` |
| 3a | `AgentAdapter._agent_error` stops redacting | `test_floor2_worker_provider_error_never_stores_or_logs_a_credential`, all 8 parametrizations (classify and courseops for each of anthropic_api, openai, zai and claude_code) |
| 3b | `anthropic_api` uses `from e` instead of `from None` | the worker pin, for both `anthropic_api` parametrizations (chained cause in Celery's trace) |
| 3d | concepts route returns `str(exc)` | `test_floor2_global_handler_never_returns_or_logs_raw_agent_error` |
| 4a | re-summarize without `snapshot_summary` | `test_floor4_resummarize_preserves_prior_version` |
| 4b | merge `keep_source` without snapshot | `test_floor4_merge_keep_source_snapshots_target_summary` |
| 4c | merge re-homes versions to the source, not the target | `test_floor4_merge_carries_moved_summarys_versions_to_target` |
| 4d | regeneration `DELETE`s flashcards again | `test_floor4_asset_regeneration_keeps_study_history`, `…every_blob_delete_is_classified` |
| 4e | leaderboard admits every user | `test_floor1_leaderboard_lists_only_opted_in_users` |
| 5a | new request-time `get_embedding_provider().embed_texts` in `api/search.py` | `test_floor3_get_embedding_provider_sites_equal_adr_0005_allowlist`, `…embed_texts_sites_equal_adr_0005_allowlist` |
| 5b | new request-time `get_agent()` in `api/search.py` | `test_floor3_request_time_get_agent_sites_equal_adr_0003_allowlist` |
| control | unmodified copy | floor1 `15 passed`, floor2 `20 passed, 6 deselected`, floor3 `13 passed`, floor4 `18 passed` |

**One mutant survived: 3c.** I disabled the `AgentError` branch in `main.studyaio_error_handler`, and the
floor-2 file stayed green (`14 passed, 12 deselected` on `-k "global_handler or provider_error"`). The test that
carries the handler's name drives `POST /api/concepts/extract/{id}`. BACKEND-013 made that route catch `AgentError`
itself, so the error no longer reaches the global handler. The test was red before BACKEND-013 and green after it,
but what it now pins is the concepts route, not the handler. I checked the handler directly instead, by calling it
with an `AgentError` that quotes an instance key:

```
[current] status: 500 | sentinel in response: False | sentinel in log: False
[mutant (AgentError branch disabled)] status: 500 | sentinel in response: True | sentinel in log: True
```

The handler fix holds in the code, but no test in the tier pins it. See follow-up F-1.

---

## Floor 1: tenant isolation

> an authenticated endpoint never returns or mutates another user's rows; every user-owned query filters on user_id

**Holds in the code: YES.**

- All seven R-015 findings are fixed. I read each one in `git diff 2da6f17 8d9de14`:
  - `api/study.py`: `post_review` and `post_quiz_attempt` now go through `srs_service.get_owned_flashcard`
    and `exam_service.get_owned_quiz_question`. Both join `Course` and filter on `Course.user_id`, and both exclude
    archived items. An optional `exam_id` is checked through `get_exam(..., user_id=)`. `record_review` also scopes
    the existing-review lookup.
  - `generate_timed_plan` takes `user_id` and scopes the exam, the due cards and the quiz query on it.
  - `qa/ask` resolves `course_code` with `course_service.get_course_by_code(..., user_id=user.id)`.
  - Week detail calls `get_summary_for_week(..., user_id=user.id)`.
  - `mark_notified(..., user_id=user.id)`.
  - `classify._get_known_courses(session, user_id)` filters `Course.user_id`. The caller passes
    `user_id or artifact.user_id`. If both are `None`, that matches only ownerless rows, so it fails closed.
- The integration xfails for all seven are gone (QA-022 deleted them). The tests are in
  `test_api_study_exams.py`, `test_api_content_reads.py`, `test_api_courses_files.py`, `test_gamification.py` and
  `test_pipeline_end_to_end.py`, and they pass in that pipeline's `integration-tests`.
- Leaderboard: `xp_service.get_leaderboard` admits a row only when `user_settings.leaderboard_opt_in` is true, or
  when the row is the caller's own. The column defaults to `False` (DATA-017). It returns no extra fields.
- New owned table `summary_versions`: `user_id` is a NOT NULL FK, and it is classified as owned. No API reads it yet.
- Both detector blind spots from SAFETY-021 were closed in SAFETY-025 and are pinned by
  `…caller_filter_detector_rejects_widened_predicates` and `…unscoped_query_detector_needs_a_predicate_not_a_mention`.

**Still open, not red:** R-010. `review_items` and `quiz_attempts` have no `user_id` and are scoped only through joins.
The sweep classifies them as owned. Unchanged.

## Floor 2: no secrets in the tree

> no plaintext credentials, tokens or keys committed, and per-user AI credentials are never logged or returned by the API

**Holds in the code: YES.** Three layers now hold, and each of the first two was shown red by mutation:

1. **Adapter boundary** (AI-014). `AgentAdapter._agent_error` → `_redact` replaces every string leaf of the adapter's
   `_api_key` and `_credentials_json`, including JSON-nested CLI tokens, and every instance key, longest first. If
   redaction itself fails, the message is withheld. All five adapters now raise through it with `from None`.
   This layer closes R-012: worker logs, `pipeline_runs.error_message` and the Celery trace.
2. **Per site.** `qa/ask`, `test-ai`, chat send and stream, and now concepts (site #5) catch `AgentError`, log
   `settings_service.redacted_error` and return a generic detail.
3. **Global handler.** For `AgentError`, `studyaio_error_handler` logs `detail="withheld"` and returns a generic
   message. This was verified directly (above). It is unpinned in the tier (F-1).

Committed-tree checks are green. The git-less scan now fails loudly (R-018, SAFETY-012), and `test-floor` passed in a
CI image.

**Still open, outside the literal floor:** R-009 (50 unaudited baseline entries). R-017 (OAuth and calendar tokens in
plaintext at rest; the Telegram webhook accepts any caller when the URL is unset).

## Floor 3: AI only via the adapter (ADR 0003 + ADR 0005)

**Holds in the code: YES. The scope is now defined.**

- R-004 was ruled on 2026-10-04: embeddings are in scope. ADR 0005 is Accepted. `get_embedding_provider` and
  `embed_texts` each have an exact allowlist, and backend classes are banned outside `app/agents/**`.
- The M31-S2 diff adds no request-time `get_agent`, `get_embedding_provider` or `embed_texts` site. In
  `git diff 2da6f17 8d9de14 -- services/app/app`, the only AI-path changes are in `app/agents/**` (redaction), the
  concepts route (an error catch around the existing site #5) and `classify.py` (a scoping filter).
- The new `txt` extractor and `classify` preview read only server-generated quick-capture text. They make no AI call.
- Mutations 5a and 5b are both red.

## Floor 4: user data is never lost (ADR 0004)

**Holds in the code: YES.**

- **Re-summarize.** `summary_service.create_or_update_summary` calls `snapshot_summary` before it mutates. The
  snapshot writes a `summary_versions` row (`content_md`, `version`) and a `Week<N>.v<k>.md` blob, and never puts over
  an existing key. The pipeline writes each version to its own versioned key, and refuses to overwrite one
  (`storage.exists` guard, AI-024).
- **Merge.** `keep_source` snapshots the target first, then writes the new version to a fresh key with
  `delete_old=False`. A week moved to the target re-homes its `summary_versions` (an UPDATE scoped to that week).
  BACKEND-026 fixed this, so the SAFETY-025 VETO pin is green and that pin was not edited. `_discard_summary` is unchanged.
- **Regeneration.** `asset_service.save_flashcards` and `save_quiz_questions` set `archived_at` and never delete. Every
  active-read query I found in the diff now excludes archived items: srs, exam, readiness, schedule, analytics,
  search, export, course weeks and notifications. Archived items cannot be reviewed or attempted (BACKEND-026).
- **Delete sites.** The only new delete in M31-S2 is `delete(SummaryVersion)` inside `course_service.delete_course`.
  ADR 0004 #1 names it verbatim (clarification of 2026-10-08), and `COURSE_DELETE_MODELS` pins it model by model.
  `DB_VIOLATIONS`, `BLOB_VIOLATIONS` and both `*_PENDING_RULING` dicts are empty.
- **Account deletion.** `delete_user_account` iterates every table by predicate, so `summary_versions` is covered
  through its `user_id`.

**Still open, not red:** R-016. `delete_user_account` hits an FK violation for users who have courseops rows (strict
xfail in `test_account_deletion_courseops.py`). That is a right-to-erasure defect on the floor's sanctioned path. It
loses no data. R-013, the courseops upload race, is unchanged.

---

## VETO-lift items (from `floors.md`, 2026-10-04)

| # | Item | Met? | Evidence (red first, then green) |
|---|---|---|---|
| 1 | Floor 1, R-015: scope the 7 findings; strict xfails XPASS, markers removed | **MET** | BACKEND-013 and AI-014. The xfails turned XPASS(strict) on the integrated branch (`7 failed` = the 7 XPASS, BACKEND-013 row). QA-022 removed the markers and re-proved them with the fixes reverted (`9 failed`). Green in that pipeline's `integration-tests`. Mutations 1a–1g are red in the floor tier as well. |
| 2 | Floor 1 sweep gap: body-borne ids, typed path params, function-level check, each shown red on R-015 code | **MET** | SAFETY-012 on the pre-fix tree: `13 failed, 38 passed`, each red a named R-015/R-012 finding. Green after BACKEND-013 and AI-014. `test_floor1_route_sweep_reaches_every_handler` fails on any validation 422, so the `json={}` blind spot cannot come back silently. Mutations 1a–1g go red through the new sweep paths, and none of them would have reached a handler under the old sweep. |
| 3 | Floor 2: redact at `AgentError` construction (`ai`); handler stops echoing (`backend`); concepts site, worker pin and stale `FLOORS.md` line (`safety`) | **MET in code**, with one pin gap (F-1) | SAFETY-012 red on the integrated branch (`9 failed`: 8 worker echoes plus classify). AI-014 turned them green (`422 passed`). Concepts is in `REQUEST_TIME_AI_ERROR_SITES`. Mutations 3a, 3b and 3d are red. The handler fix is verified by direct call but not pinned (3c survived). The specific stale line ("RED today" at qa/chat) is gone, but other `RED until` notes in `FLOORS.md` are now stale too (F-2). |
| 4 | R-007 rulings (leaderboard, re-summarize, regeneration, single-item deletes) implemented | **MET** | The rulings are recorded in `docs/decisions.md` (2026-10-04). ADR 0004 is Accepted, with an amendment and a clarification. SAFETY-021 landed `5 failed` (exactly the BACKEND-019 pins), and BACKEND-019 made them green with no test edit. SAFETY-025 found one more hole, the merge pin (`1 failed`), which BACKEND-026 made green with no test edit. Mutations 4a–4e are red. |
| 5 | Floor 3, R-004 embeddings ruling and pin | **MET** | Ruled 2026-10-04 (in scope). ADR 0005 is Accepted. SAFETY-021 showed 13 injected violations red in a scratch copy. Mutation 5a is red. |

## Regression spot-check (M31-S2 diff, `2da6f17..8d9de14`, `services/app/app`)

- **New delete sites:** one, `delete(SummaryVersion)` in `delete_course`. It is sanctioned and bounded. The
  `_sync_summary_blob` default `delete_old=True` still deletes the old key when a week moves. That is the existing
  move site, which is classified. The `keep_source` path passes `delete_old=False`, because the old key is now a
  retained version's blob. That is correct.
- **New request-time AI or embedding sites:** none.
- **New unscoped functions:** `summary_service.snapshot_summary` reads `Course.user_id` by `summary.course_id`. That is
  FK traversal from a row the caller already holds, and it is classified (SAFETY-025). No other new query lacks a
  caller predicate.
- **New credential surfaces:** `leaderboard_opt_in` was added to `SettingsResponse` and `SettingsUpdateRequest`.
  It is not a credential, and `test_floor2_settings_schemas_carry_no_credential_value` passes.

## Threat-model delta since 2026-10-04

**Closed**
- R-015: the 7 cross-tenant read/write paths (F1). This includes the cross-tenant disclosure of course codes to the
  AI provider in classify prompts.
- R-012 and concepts site #5: provider-error credential echo in worker logs, in `pipeline_runs.error_message`, in the
  Celery trace and in the API response and log (F2).
- Global `StudyAIOError` handler echo for `AgentError`. Other `StudyAIOError`s still return `str(exc)`. They are
  raised by our own code with deliberate messages, so the residual is information disclosure, not credentials.
- R-004 (floor 3 scope) and R-007 (four rulings) are resolved. R-018: the git-less scan now fails loudly.
- The floor-1 detector blind spots (OR, NOT, `!=`, widened IN; mention-as-predicate) are closed.

**New or changed exposure**
- **More retained data means a wider erasure surface.** Prior summary versions (rows and blobs) and archived
  cards and questions are now kept indefinitely. Account deletion removes the rows. The blob purge, however, sweeps
  `summaries/<course_id>` only for courses **still in the DB at account deletion**
  (`account_service.purge_user_storage`). Course delete keeps blobs by design (ADR 0004 #1). So every summary blob of
  a course deleted before the account, which now includes all retained `Week<N>.v<k>.md` versions, is **never
  purged**. That includes the version blobs of summaries re-homed by merge: they stay under the archived source's
  prefix, so once that source course is deleted they leave the purge's reach. ADR 0004 #1 says "The account purge
  sweeps the user's prefix later". That is inaccurate, because summary keys are per course, not per user. This is
  not a floor-4 breach, since nothing is lost. It is a GDPR erasure gap, pre-existing for current summaries and
  widened by M31-S2 retention. Raise it as a new risk (F-3).
- **The fail-open optional `user_id` pattern is now widespread.** `mark_notified`, `get_summary_for_week`,
  `generate_timed_plan`, `record_review` and `get_due_cards` all take `user_id: str | None = None` and skip the filter
  when it is `None`. Every route caller passes it, and the route sweep pins that. The function-level detector accepts
  any function that "uses" a caller parameter, though, so a future **non-route** caller that omits it would run
  unscoped and nothing would fail. The same shape is already noted in ADR 0004 for `delete_course_document` and
  `delete_deadline` (F-4).
- **Leaderboard:** now opt-in. For a user who opts in, username and XP are disclosed to every user, by the user's
  choice.
- **Quick-capture `txt` artifacts** now reach classify and the AI prompts. This is the same prompt-injection class as
  every uploaded document, not a new class.

**Unchanged and still open:** R-009, R-010, R-011 (process), R-013, R-016, R-017.

## Follow-ups (non-blocking; none is a floor red in the code)

- **F-1 (`safety`).** Re-target `test_floor2_global_handler_never_returns_or_logs_raw_agent_error` so that it reaches
  `studyaio_error_handler`. Either call the handler directly, or use a route that does not catch `AgentError`. Show it
  red with the `AgentError` branch disabled. Today mutant 3c survives.
- **F-2 (`safety`).** Remove the stale `RED until` annotations from `tests/safety/FLOORS.md`: the floor-1 sweep rows,
  the unscoped-function row, the three floor-2 echo rows and the merge-carries row. All of them are green.
- **F-3 (Orchestrator → `/risk`; `backend` and `architect`).** Account purge never sweeps the summary blobs of deleted
  courses, now including retained versions. Fix the ADR 0004 #1 wording, and either sweep by the `file_path` values in
  `summaries` and `summary_versions` at deletion time, or key summaries per user.
- **F-4 (`backend`, `safety`).** Make `user_id` a required keyword on the newly scoped service functions, or extend
  the function-level check to fail when a scoped function's `user_id` defaults to `None`.
- **Doc drift (`architect`):** ADR 0003's header still says ADR 0005 is "(proposed)". ADR 0005 is Accepted.

Verdict: APPROVE

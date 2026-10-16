# Floor tier — floor to test map

The floor tier is `services/app/tests/safety/`, owned by `safety`. Every test runs
without Postgres, Redis or Docker: AST checks over `app/**`, FastAPI's test client
with dependency overrides, and mock sessions that record the SQL a handler builds.

Floors are quoted from `docs/strategy.md` §6. A floor is **green** only when every
test listed for it passes. A floor question that only the user can decide is held
in a `*_PENDING_RULING` dict, and a test per floor is red while that dict is not
empty. The 2026-10-04 rulings emptied every one of them. The tier holds no `xfail`:
the SAFETY-027 veto marker on the JWT default-secret check (floor 2) XPASSed on
`8356b15` and was removed in SAFETY-028. SAFETY-033 added two **strict** `xfail`s on the
email-redaction *backstop* (SEC-08), findings F1 and F2; both fixes landed (`06c4fcb`, `344ce7e`) and
SAFETY-040 promoted them to plain tests, so the tier is again `xfail`-free. A test marked **RED until** names the task whose code change it waits on; none is marked at the M32 gate. At M33-S2, `test_floor4_recovered_row_gets_no_items_inserted_later` waited on M33-S2-AI-053 as a strict `xfail`; the fix landed in the same task and the marker was removed, so the tier is `xfail`-free.

Run:

```
cd services/app && .venv/bin/python -m pytest tests/safety -v
```

## 1. Tenant isolation

> an authenticated endpoint never returns or mutates another user's rows; every
> user-owned query filters on user_id

| Test | Fails when |
|---|---|
| `test_floor1_tenant_isolation.py::test_floor1_route_sweep_every_owned_query_filters_on_caller` | Any authenticated, non-admin route (every method), called with a type-valid request that carries a foreign value in every path parameter, every required query parameter and every JSON body field (`_payload.py` builds it from the route's own types; upload routes get a real PDF file part, `_upload_files`), runs a statement on a user-owned table that does not compare `user_id` to the caller's id. It also fails if `session.get()` is called on an owned model. It also fails if the sweep reaches fewer than 90 routes that query an owned table (74 at the M31 gate, 98 at M32-S4), because below that the check proves nothing. A request the harness cannot build now fails the test; until M32-S4 it was caught as if the handler had crashed, and 27 routes with a query parameter went unswept that way on fastapi 0.136 (`ModelField.required` removed). A handler that opens its own session (`async_session_factory`, the upload XP award) is given the recording mock too. Green since M31-S2-BACKEND-013 fixed R-015 (`qa/ask`, `study/review`, `study/quiz-attempt`, `study/timed-plan`, `gamification/achievements/mark-notified`). |
| `…::test_floor1_route_sweep_owned_parent_never_unlocks_foreign_rows` | Same sweep, but every lookup that is scoped to the caller finds a row the caller owns, so handlers get past their ownership check. Fails when a later statement on an owned table is keyed on request input alone: it binds a planted value that no caller-scoped primary-key lookup has vetted, binds no id of the caller's own row, and has no `user_id` filter. A course *code* is never vetted, because it is unique per user, not globally. Green since BACKEND-013 (R-015: `GET /courses/{code}/weeks/{n}`, plus the five routes above). |
| `…::test_floor1_route_sweep_reaches_every_handler` | A swept route is still rejected by FastAPI's request validation (a 422 with a field-error list), so its handler never runs and the sweep cannot see it. `SWEEP_UNREACHED_BY_DESIGN` is empty since M32-S4: the four multipart upload routes are sent a file part and swept. It also fails if any route in `SWEEP_MUST_QUERY_OWNED` (those four) stops reaching a query on an owned table, or if a listed route starts reaching its handler. Mutation-checked in SAFETY-029: dropping `Course.user_id` from `_get_course_owned` flags `POST …/assessments/{id}/documents`; unscoping `get_course_by_code` in `upload_course_document` flags `POST /courseops/documents`. |
| `…::test_floor1_route_enumeration_is_not_vacuous` | `app.routes` yields fewer than 130 `/api` `APIRoute`s (149 at M32-S4) or the sweep enumerates fewer than 100 method+path pairs (115). **`fastapi` is capped `<0.137` in `requirements.txt` for this reason**: 0.137 makes `include_router` lazy, so `app.routes` holds `_IncludedRouter` placeholders, and every guard that walks it (this sweep and `tests/unit/api/test_endpoint_authn_guard.py`; the scoping guard reads source, not routes) iterates nothing and passes. Lifting the cap means expanding those placeholders in `_sweep_routes` and the authn guard first. Mutation-checked: replacing the `/api` routes with an `_IncludedRouter` stand-in fails here. |
| `…::test_floor1_payload_builder_plants_type_valid_foreign_values` | The request builder (`_payload.py`) stops producing a body that validates for a declared type (bounds, enums, literals, dates, UUIDs, nested models, a model-level "one of" rule), or stops planting a recognisable foreign value. The sweep is only as wide as this builder. |
| `…::test_floor1_every_table_is_classified` | A table is neither user-owned (it has `user_id`, a FK to an owned table, or is polymorphic) nor listed in `UNOWNED_TABLES`. |
| `…::test_floor1_no_unscoped_session_get_on_owned_model` | An `api/` or `services/` function calls `session.get(OwnedModel, <its own parameter>)` and the call is not classified. It also fails on a stale classification. SAFETY-013 removed `_get_course_owned` (its `user_id=None` branch went in BACKEND-006) and mutation-checked that restoring the branch fails here. |
| `…::test_floor1_no_unscoped_query_function_outside_classification` | A `services/` or `pipeline/` function builds a query on a user-owned model, takes no caller parameter (`user_id`, `user`, …) that it uses, and puts no `<Model>.user_id` predicate or `filter_by(user_id=)` in it, and the function is not in `UNSCOPED_FUNCTION_ALLOWED` with a reason (worker-only, webhook, token lookup, FK traversal from a scoped parent). It also fails on a stale entry. This reaches code no route sweep can. Green since BACKEND-013 and AI-014 (R-015: `classify._get_known_courses`, `achievement_service.mark_notified`, `summary_service.get_summary_for_week`, `timed_session_service.generate_timed_plan`). SAFETY-024 classified `_owner._row_owner_async` (R-022: worker-only owner lookup for the SSE channel; returns an id, fails closed). M33-S2-SAFETY-024 classified `targeted_task._claim` and `targeted_task._recover_stuck` (ADR 0007; see the weak-spot section). |
| `…::test_floor1_unscoped_query_detector_is_not_vacuous` | The detector stops seeing two known worker-side unscoped reads. |
| `…::test_floor1_unscoped_query_detector_needs_a_predicate_not_a_mention` | On synthetic source, the detector counts a join on `Model.user_id` (`UserXP.user_id == User.id`) or a selected `Course.user_id` as a `user_id` predicate, or flags a real `== value`/`.in_()` predicate. Closed SAFETY-021 blind spot 2 in SAFETY-025; that surfaced `snapshot_summary`, `notify_admins` and `backfill_courseops_storage_keys`, all classified. |
| `…::test_floor1_caller_parameter_is_never_optional` | A `services/` or `pipeline/` function uses a caller parameter (`user_id`, `user`, …) that defaults to `None`, or puts a `user_id` filter behind a `None`/truthiness check on it (`if user_id is not None: query = query.where(...)`), and is not in `OPTIONAL_CALLER_ALLOWED` with a reason. Such a function is scoped only when its caller remembers to pass the identity; the route sweep pins today's route callers, but a worker, CLI or service caller that omits it reads or writes every user's rows. R-021 (M31 re-run F-4, M32 condition C6). Green since M32-S1-BACKEND-006 (`d1276a0`: 71 functions at `d37528f` made keyword-only required with unconditional filters) and M32-S1-AI-012 (`8812e4a`: `classify._get_or_create_course` takes a required owner and raises on `""`). SAFETY-009 classified ten pipeline functions under the C6 ruling (the six artifact stages and the concepts task act for `artifact.user_id`; `_ingest` fails closed on the NOT NULL users FK; the two orchestrator dispatchers run no query). SAFETY-013 mutation-checked it red with `get_review_item` back to `user_id: str \| None = None`, with `get_course_document`'s filter behind `if user_id:`, and with `_get_or_create_course` back to `if user_id:`. It also fails on a stale entry. |
| `…::test_floor1_row_owner_stages_never_use_a_bare_optional_caller` | A stage classified `_ROW_OWNER` in `OPTIONAL_CALLER_ALLOWED` reads `user_id` anywhere other than inside a `warn_on_owner_mismatch(...)` call. The allowlist is keyed on the function, so without this a later edit that hands the possibly-`None` payload owner to a scoped service would pass, and so would one that lets the payload override the row again (`user_id or artifact.user_id`), which spends B's credentials and billing on A's artifact. Tightened in SAFETY-013 after AI-012 (`8812e4a`) made the row win. Mutation-checked: `_get_known_courses(session, user_id)` in `_classify` and `owner_id = user_id or artifact.user_id` in `_summarize` both fail here. |
| `…::test_floor1_optional_caller_detector_is_not_vacuous` | On synthetic source, the R-021 detector stops flagging a `None` default (positional or keyword-only), a filter skipped on `if user_id:`, or a function that forwards a `None`-defaulted caller, or starts flagging a required caller, a fail-closed `if user_id is None: raise`, or an unused caller parameter. |
| `…::test_floor1_caller_filter_detector_rejects_widened_predicates` | `_tenant.filters_on_user` reads `user_id = :caller OR …`, `NOT (user_id = :caller)`, `user_id != :caller` or `user_id IN (:caller, :victim)` as caller-scoped, or stops accepting `= :caller`, `IN (:caller)` or an OR whose every branch is caller-scoped. Closed SAFETY-021 blind spot 1 in SAFETY-025; every sweep test runs on this helper. |
| `…::test_floor1_insert_detector_accepts_only_caller_owned_writes` | `_tenant.inserts_for_caller` accepts an INSERT for another user, a multi-row VALUES with one foreign row, an `INSERT … SELECT`, an upsert whose conflict key lacks `user_id` or carries an update `WHERE`; or rejects the caller's plain insert or `(user_id, record_date)` upsert. Added in SAFETY-026 when GL#19 (`f5960c8`) made `record_usage` an atomic `INSERT … ON CONFLICT (uq_usage_user_date) DO UPDATE` and the sweep flagged it (an INSERT has no WHERE). The sweep now accepts a statement that passes this helper. Mutation-checked: `record_usage` writing another `user_id`, or conflicting on `record_date` alone, turns the route sweep red. |
| `…::test_floor1_pipeline_only_fetch_is_pipeline_only` | The one allowlisted worker-only unscoped fetch gains a caller outside `app/pipeline/`. |
| `…::test_floor1_chunk_store_is_worker_only` | `index_service.store_artifact_chunks` (deletes and rewrites an artifact's chunks by a bare `artifact_id`) is referenced outside `app/pipeline/` other than from its wrapper `index_artifact_chunks`, or the wrapper is referenced outside `app/pipeline/` at all; or neither is referenced from the worker (blind detector). A request-side caller with a foreign artifact id would wipe another user's search index. Added in M34-S3-SAFETY when AI-010 split the index service. Mutation-checked: a reference from `app/services/chat_service.py` fails it. |
| `test_floor1_anonymous_caller.py::test_floor1_self_hosted_anonymous_caller_is_401_on_every_user_route` | SEC-05 (GL#25, R-035). On a `SELF_HOSTED`, multi-user instance (`SINGLE_USER_MODE` off), any route that requires a user, admin routes included, answers a request with no session cookie with anything but 401, or the default admin is resolved at all. Fails if fewer than 120 user-requiring method+path pairs are enumerated. Added at the M32 gate because the unit tier alone (`tests/unit/test_single_user_mode.py`) pinned the dependency. Mutation-checked: `get_current_user_or_default` falling back to the default admin on `self_hosted` alone resolves it 103 times and fails here. |
| `…::test_floor1_single_user_mode_control_reaches_the_default_admin` | Control: with `SINGLE_USER_MODE` on, the same anonymous harness never reaches the default-admin fallback, so the 401 pin above could not tell a fixed dependency from a broken harness. |
| `test_floor1_worker_jobs.py::test_floor1_recovery_job_is_worker_only` | TECH-04 (GL#22, `b011c3d`). A module other than `app/pipeline/recovery.py` and `app/worker.py` imports the recovery job, calls `_recover`/`recover_stuck_artifacts`, or names the task in a (non-docstring) string such as `send_task(...)`. The job reads every user's in-progress artifacts; `_recover` is classified in `UNSCOPED_FUNCTION_ALLOWED` on this condition (SAFETY-027). |
| `…::test_floor1_recovery_requeues_each_artifact_as_its_own_owner` | One batch with two users' stuck artifacts resumes either with anything but that artifact row's own `user_id`. Mutation-checked: reusing the first row's owner fails here. |
| `…::test_floor4_recovery_never_deletes` | Requeue or give-up issues a `session.delete`, an executed `DELETE`, or `recovery.py` calls any `delete`/`remove`/`unlink`/`rmtree`. Giving up only sets `failed`. |
| `…::test_floor1_webhook_mutates_only_the_named_customers_row[…]` | BILL-01 (GL#21, `b7974d1`). A Stripe `subscription.updated`/`deleted` event changes a subscription or user tier other than the named customer's and that row's own `user_id`, or a lookup is keyed on anything else. Mutation-checked: keying the user lookup on a constant fails here. |
| `…::test_floor1_webhook_replayed_or_stale_event_mutates_nothing`, `…::test_floor1_webhook_old_subscription_delete_keeps_the_current_one` | A replayed event id or an event older than the customer's last applied one runs any query, or a superseded subscription's delete downgrades the customer. Mutation-checked: disabling the `SET NX` dedupe fails here. |
| `…::test_floor1_cannot_attach_document_to_another_users_assessment` | `attach_assessment_document` lets user B attach a document to user A's assessment. The fake session answers like a database: only a lookup filtered on the caller's `user_id` comes back empty, so an unscoped `select` fails too, and a control call as the owner must find the row. Fixed in M31-S1-BACKEND-008 (`a2cd687`). |
| `…::test_floor1_no_cross_user_route_awaits_a_ruling` | `SWEEP_PENDING_RULING` is not empty: some route reads across users and the user has not ruled on it. Empty since the 2026-10-04 rulings; the leaderboard moved to `SWEEP_OPT_IN_CROSS_USER`. |
| `…::test_floor1_leaderboard_lists_only_opted_in_users` | `GET /api/gamification/leaderboard` runs a `user_xp` statement that, evaluated row by row (`_predicate.admits`), keeps another user who opted out or has no `user_settings` row, or drops one who opted in. The caller's own row is unconstrained. It also fails if the route runs no `user_xp` query, or uses SQL the evaluator does not model. The leaderboard is exempt from the sweep (`SWEEP_OPT_IN_CROSS_USER`) because the sweep asks whether `user_id` is compared to the caller, which cannot judge an opt-in filter. Ruled 2026-10-04 (R-007): opt-in, hidden by default. Green since M31-S2-BACKEND-019 (`leaderboard_opt_in`). |
| `…::test_floor1_predicate_evaluator_models_sql_semantics` | `_predicate.admits` stops keeping exactly the rows Postgres would: three-valued logic, outer joins that null the unmatched side, IN over lists and subqueries. It also fails if an unmodelled construct stops raising `Unreadable`. |
| `test_floor1_owner_routing.py::test_floor1_pipeline_events_publish_to_a_resolved_owner` | A pipeline `publish_pipeline_event[_sync]` call names a recipient that is not a local assigned only from `resolve_event_owner(...)` (the artifact-row owner lookup), or a pipeline event is published outside `app/pipeline/`. The R-022 bug (publishing to the Celery payload `user_id`) fails here. Green since M32-S1-AI-021 (`1d08ef4`). A *relay* (a helper publishing to its own keyword-only parameter, TECH-04's `resilience.handle_retryable`) is accepted only if it never reassigns that parameter and every call site, inside `app/pipeline/`, passes a resolved local; SAFETY-027 added this when `b011c3d` turned the test red on a correct relay. Mutation-checked: `summarize_artifact` passing the payload `user_id` to `handle_retryable` fails here. |
| `…::test_floor1_payload_user_never_receives_another_owners_stage_event[<stage>]` | For classify/extract/summarize/index/assets, with the row owned by A and the payload naming B, any outcome (completed, waiting_review, non-retry error, retry) publishes to B's channel. |
| `…::test_floor1_unknown_row_owner_drops_stage_events[<stage>]` | A missing row makes a stage publish to anyone (it must pass `None`, which the publisher drops) instead of guessing the payload user. |
| `…::test_floor1_ingest_with_precreated_row_never_reaches_payload_user[<outcome>]`, `…::test_floor1_ingest_without_row_uses_payload_user_only_before_the_row_exists` | Ingest with a pre-created artifact (every upload) reaches the payload user for a row owned by another, or guesses on an unknown row; or, with no pre-created row, the placeholder (`pending`/`unknown`) events stop going to the payload user (who creates and so owns the row) or the result event for the row the run produced is not re-resolved from that row. Ruled acceptable in SAFETY-024: the pre-row events carry only a placeholder id and the payload user's own file. |
| `…::test_floor1_event_owner_lookup_fails_closed`, `…::test_floor1_publisher_drops_an_ownerless_event`, `…::test_floor1_row_owner_lookup_is_worker_only` | `resolve_event_owner` falls back to the payload owner on a miss or error, the publisher opens a channel for a `None` owner, or the unscoped `_row_owner[_async]` lookup (classified in `UNSCOPED_FUNCTION_ALLOWED`) gains a caller outside `app/pipeline/`. |
| `…::test_floor1_chat_unowned_course_code_is_indistinguishable_from_missing[<msg>]` | A course code typed into chat (GL#10, BACKEND-019) that another user owns yields a different plan (reply text, quiz action, scope) or a different number of statements than a code nobody owns, i.e. chat becomes an existence oracle for other users' course codes. The fake session finds the row for any lookup not filtered on the asking non-owner, so a dropped filter is visible; the control (owner) must resolve it. Mutation-checked in SAFETY-024: unscoping `get_course_by_code`, or branching a miss on an unscoped probe, both fail. |
| `…::test_floor1_chat_sources_come_only_from_caller_scoped_chunks` | Stored chat sources name a chunk or artifact outside the caller-scoped `search_chunks` result, e.g. from the adapter's own citation list (model output). |
| `test_floor1_owner_routing.py::test_floor1_chat_carried_foreign_course_is_indistinguishable_from_missing[…]` | GL#31. A course code another user owns, named in an earlier turn, carries scope into a follow-up, or yields a different plan or statement count than a code nobody owns. Control: the owner's code is carried. |
| `…::test_floor1_chat_bare_week_lists_only_the_callers_courses[…]` | "Which course for Week N" names, or scopes to, another user's course, or differs from an empty database for a non-owner. |
| `…::test_floor1_chat_scope_carry_adds_no_ai_call_site` | `_carry_scope`, `_courses_with_week` or `_plan_message` calls an adapter (the clarifying reply is a template). |

Mutation-checked in SAFETY-026, all caught: carried code looked up unscoped; week listing with no owner filter; week listing filter OR-widened. An extra unscoped probe whose result is not used survives, correctly: output and statement count stay equal, so it discloses nothing.

| Test | Fails when |
|---|---|
| `test_floor1_study_nudge.py::test_floor1_nudge_candidate_subqueries_are_each_correlated_to_the_candidate` | PROD-03 (GL#15). An EXISTS sub-query in `nudge_service.candidates_stmt` (opt-in, studied, reviewed, uploads) lacks `<table>.user_id = users.id` as a plain AND conjunct, so another user's rows decide who is nudged. A correlation under OR also fails. |
| `…::test_floor1_nudge_selection_returns_ids_not_other_users_data` | The cross-user selection returns a column other than `users.id` and booleans (an email, a zone, content). |
| `…::test_floor1_nudge_selection_is_worker_only` | A module outside `app/pipeline/`, `app/worker.py` and `nudge_service` itself imports `nudge_service` or names `find_nudge_candidates`/`candidates_stmt`. |
| `…::test_floor1_nudge_delivery_is_keyed_on_the_candidate_only[…]` | `send_study_nudge` writes an inbox row for anyone but the candidate, or runs a statement on an owned table (or `users`) not filtered on the candidate. |
| `…::test_floor1_preference_seeding_writes_and_reads_only_the_new_users_rows`, `…::test_floor1_signup_seeds_preferences_for_the_user_just_created[…]` | Default-preference seeding creates or looks up rows for anyone but the new user, or one of the three signup paths (`register_user`, `create_or_link_oauth`, admin `create_user`) seeds for anything but `user.id` of the row it just created. |
| `…::test_floor1_course_quota_reads_only_the_row_owners_tier_and_count` | GL#19 (ai AI-029, `447efb4`). `classify._get_or_create_course` checks the course quota for anyone but the owner it was given, reads the tier from a `users` row not keyed on that owner (`users` is unowned to the sweep, so nothing else sees it), looks up courses unscoped, or writes/deletes anything on refusal. Mutation-checked: `select(User.tier).limit(1)` fails here; passing the payload `user_id` instead of `artifact.user_id` fails `test_floor1_row_owner_stages_never_use_a_bare_optional_caller`. |
| `…::test_floor2_email_unsubscribe_link_is_static_and_carries_no_token_or_pii[<sender>]` | Any `email_service.send_*` email lacks the footer unsubscribe link, or the link is anything but the static `<app_base_url>/settings/notifications` (no token, address or id; a signed one-click link would be a credential in every inbox and mail log). |

Mutation-checked in SAFETY-026 (scratch copy, `scratchpad/mutate.py`), all caught: `studied` uncorrelated; opt-in correlation OR-widened; `User.email` selected; a route importing `find_nudge_candidates`; seeding for another owner; inbox row to another user; unsubscribe URL carrying the recipient.

### AI feedback votes and usage events (GL#36, GL#37; backend `61694a6`)

Pinned in M33-S1-SAFETY-033 over MiniDB (`_minidb.py`), so a dropped predicate changes
the answer instead of hiding behind a mock that returns `None`. The two cross-user
aggregates are classified in `UNSCOPED_FUNCTION_ALLOWED` (`ai_feedback_service.admin_summary`,
`usage_service.retention_readout`) on the conditions pinned here.

| Test | Fails when |
|---|---|
| `test_floor1_ai_feedback_usage.py::test_floor1_vote_on_foreign_target_is_a_404_identical_to_missing[<type>]` | For any target type, `PUT /api/feedback` on another user's summary, answer, chat message, flashcard or quiz question is not a 404 with the same body as a missing id (no cross-type existence oracle), or writes a vote or a usage event. |
| `…::test_floor1_vote_on_own_target_is_stored_for_the_caller[<type>]` | The stored vote, its `course_id` or the `feedback_given` usage event is not the caller's. |
| `…::test_floor1_every_feedback_target_type_is_seeded` | `TARGET_TYPES` gains a type the two tests above do not seed. |
| `…::test_floor1_list_mine_returns_only_the_callers_votes`, `…::test_floor1_delete_never_removes_another_users_vote` | `GET /feedback/mine` returns another user's vote (even on the caller's own target id), or `DELETE` removes one. |
| `…::test_floor1_usage_event_rejects_a_foreign_course`, `…::test_floor1_usage_event_is_recorded_for_the_caller[…]` | `POST /usage-events` accepts another user's `course_id`, or stores a row for anyone but the caller. |
| `…::test_floor1_every_usage_record_uses_the_callers_id`, `…::test_floor1_usage_record_detector_is_red_on_another_users_id` | A `usage_service.record` call outside `app/api/`, or one whose user argument is not `<caller>.id` of the handler's `Depends(get_current_user[_or_default])` parameter. |
| `…::test_floor1_admin_aggregates_are_called_only_from_their_admin_route[…]`, `…::test_floor1_admin_aggregate_routes_require_the_admin_role[…]`, `…::test_floor1_admin_gate_detector_is_red_without_the_role` | `admin_summary`/`retention_readout` are referenced anywhere but `ai_feedback.admin_ai_feedback`/`usage.retention`, or those routes lose `require_role("admin")` (a role list wider than admin also fails). |
| `…::test_floor1_admin_feedback_summary_carries_no_user_identifier`, `…::test_floor1_retention_readout_projects_no_user_identifier`, `…::test_floor1_projection_detector_is_red_on_a_user_id` | The feedback aggregate returns a user id, target id or identifying key, or the retention queries project a bare `user_id`/`id`/`email`/`username` column (aggregates over them are fine). |

Mutation-checked in SAFETY-033, all red: chat-target owner predicate dropped; `AIFeedback.user_id`
predicates dropped; usage record with another user's id; the foreign-course check removed;
`require_role("admin")` swapped for a plain caller on the retention route; `admin_summary` called from
`GET /feedback/mine`.

### User-authored study items and upload placement (GL#48, GL#49; backend `3c1ef9c`, SAFETY-059)

`test_floor1_study_item_crud.py`, real routes and services over MiniDB with two users.

| Test | Fails when |
|---|---|
| `…::test_floor1_foreign_item_edit_or_delete_is_404_like_missing[…]` | `PATCH`/`DELETE /api/assets/{flashcards,quiz}/{id}` on B's item answers other than the missing-id 404, changes any column of B's item or review, or writes a row. |
| `…::test_floor1_create_cannot_target_a_foreign_course_or_lecture[…]` | `POST /api/assets/{flashcards,quiz}` with B's course code or B's `source_artifact_id` is not a 404 or writes a row; or the caller's own create lands outside their course and latest lecture. |
| `…::test_floor4_flashcard_edit_archives_the_original_and_keeps_its_history` | Editing removes or rewrites the original card (its AI text), drops its review row, or the copy's schedule is not the caller's own. |
| `…::test_floor4_quiz_edit_archives_the_original` | Editing removes or rewrites the original question. |
| `…::test_floor4_item_delete_is_a_soft_delete[…]` | `DELETE` removes the row (rather than setting `archived_at`) or drops review history. |
| `…::test_floor1_upload_placement_never_resolves_a_foreign_course` | `course_service.get_or_create_course` (explicit upload placement) returns B's course for B's code, misses the caller's own in another case, or checks the course quota for anyone but the caller. |

Revert-checked in SAFETY-059: `_owned_item` without `Course.user_id` (4 red); the artifact lookup
without both the owner and the course predicate (2 red; either alone still scopes it, so green);
archive/edit as `session.delete` (4 red, and the floor-4 delete inventory); `get_or_create_course`
unscoped (red). The route wiring is pinned in `tests/unit/api/test_asset_items_api.py` and
`test_upload_placement.py`: every `user_id=user.id` swapped for another value turns 10 and 2 of
them red.

### Retrieval relevance floor and follow-ups (GL#35; `a290904`..`3f5e506`)

| Test | Fails when |
|---|---|
| `test_floor1_retrieval_followup.py::test_floor1_every_chunk_search_carries_the_callers_id`, `…::test_floor1_search_scope_detector_*` | A `search_chunks` (or chat's `_search`) call passes a user that is not the enclosing function's `user_id` parameter or `<caller>.id`. |
| `…::test_floor1_followup_query_uses_only_the_callers_own_history[…]` | Send and stream, over MiniDB: the follow-up retrieval query folds in anything but the caller's own previous message from the caller's own session (another user's newer message is seeded as bait), or the search is not keyed on the caller. |
| `…::test_floor1_foreign_session_is_refused_before_any_embedding[…]` | A foreign chat session reaches embedding, search or the agent, or writes a message. |

Mutation-checked in SAFETY-033, all red: `_search` keyed on another user; the history query's
`session_id` filter replaced by `role == "user"`.

The deeper layers live in other tiers: `tests/integration/test_idor_row_level.py`
runs against a real database, and `tests/unit/api/test_endpoint_scoping_guard.py`
plus `test_idor_scoping.py` cover endpoint wiring.

## 2. No secrets in the tree

> no plaintext credentials, tokens or keys committed, and per-user AI credentials
> are never logged or returned by the API

| Test | Fails when |
|---|---|
| `test_floor2_no_secrets.py::test_floor2_settings_get_never_returns_a_stored_credential` | `GET /api/settings` contains any stored per-user credential. |
| `…::test_floor2_settings_put_never_echoes_a_credential` | The `PUT /api/settings` response echoes one back, or the stored value is not `enc:v1:` ciphertext that decrypts to what was sent (SEC-06; the test run has a throwaway key from the root `conftest.py`). |
| `…::test_floor2_credentials_never_persisted_in_plaintext_when_multi_user[saas\|self_hosted]` | Outside `SINGLE_USER_MODE`, any `SECRET_KEYS` value written through `PUT /api/settings` lands in `settings_json` without the `enc:v1:` prefix, contains the plaintext, or does not round-trip through `secret_box.decrypt`. Added SAFETY-028 (SEC-06, GL#20, `aa992ca`). Mutation-checked: dropping the `secret_box.encrypt` loop in `update_user_settings` fails it. |
| `…::test_floor2_multi_user_without_key_refuses_to_store_a_credential` | Outside `SINGLE_USER_MODE` with no `SETTINGS_ENCRYPTION_KEY`, the PUT does not answer 422 naming the key, or the row or the 422 body carries a credential. |
| `…::test_floor2_ciphertext_shaped_input_is_never_stored_verbatim` | A submitted value starting `enc:v1:` is stored as-is instead of encrypted (the pre-`8356b15` pass-through). Mutation-checked: restoring the `is_encrypted` early return in `secret_box.encrypt` fails it. |
| `…::test_floor2_multi_user_startup_refuses_without_encryption_key` | Lifespan starts a multi-user instance (`SELF_HOSTED=true`, `SINGLE_USER_MODE=false`) without `SETTINGS_ENCRYPTION_KEY`, or refuses single-user mode on loopback without one. Mutation-checked: keying `secret_box.check_startup` on `self_hosted` fails it. |
| `…::test_floor2_settings_schemas_carry_no_credential_value` | `SettingsResponse` gains a credential-valued field, or `SettingsUpdateRequest` gains a credential input that is not in `SECRET_KEYS`. |
| `…::test_floor2_account_export_never_returns_a_stored_credential[legacy_plaintext\|ciphertext]` | `GET /api/auth/account/export` returns any stored credential from `user_settings.settings_json`, including the token nested in `claude_cli_credentials`, or (ciphertext case, SAFETY-028) any `enc:v1:` value. Fixed in M31-S1-BACKEND-008 (`b5f57e6`). |
| `…::test_floor2_provider_error_never_echoes_a_stored_credential[<site>]` | A provider error that quotes every stored credential (the nested CLI token too) reaches the response, a structlog event or a stdlib log record at a request-time AI call site: `POST /api/settings/test-ai`, `POST /api/qa/ask`, `chat_service.send_message`, `chat_service.stream_message`, `POST /api/concepts/extract/{artifact_id}`. It also fails if no provider was called. The first four are green (R-008: `7eecbac` for test-ai, `718faa0` for qa and chat). The concepts site (ADR 0003 #5) runs the real adapter against a provider SDK that echoes the key it was sent (`_ProviderEcho`). Green since M31-S2-AI-014 (redaction at `AgentError` construction, R-012) and BACKEND-013 (the concepts route catches `AgentError`). |
| `…::test_floor2_worker_provider_error_never_stores_or_logs_a_credential[<site>-<backend>]` | Run eagerly as Celery tasks, `classify_artifact` and `process_course_document` hit a provider that echoes the key, for each of `anthropic_api`, `openai`, `zai` and `claude_code` (CLI stdout echoing the OAuth token). Fails if the credential reaches `pipeline_runs.error_message`, a structlog event, a stdlib log record (Celery's own `raised unexpected` line included) or the exception the task ends with. Green since AI-014 (R-012; before it, classify stored the key in `pipeline_runs.error_message` and courseops logged it as `courseops_document_failed`). |
| `…::test_floor2_global_handler_never_returns_or_logs_raw_agent_error[<path>]` | An `AgentError` (a subclass of it, built outside the adapter so it carries raw text) that reaches `main.studyaio_error_handler` leaves the provider's text, the instance key or any per-user key in the response, a structlog event or a stdlib log record. Two paths: a direct call to the handler, and a probe route mounted for the test that lets the error escape, so FastAPI's own dispatch chooses the handler. Until M32-S1-SAFETY-004 this drove `POST /api/concepts/extract`, which BACKEND-013 made catch `AgentError` itself; from then on the test never reached the handler, and disabling the handler's `AgentError` branch left it green (M31 re-run mutant 3c, F-1). Now shown red on three handler mutants: the branch disabled, the branch narrowed to `type(exc) is AgentError`, and the branch logging `str(exc)`. |
| `…::test_floor2_credentials_never_logged` | A stored credential appears in a structlog event or a stdlib log record during save, rejected save, or adapter construction for any backend. It also fails if one appears in a 422 body. |
| `…::test_floor2_no_high_confidence_secret_in_tracked_files` | A tracked file contains a private key block, or an AWS, Anthropic, OpenAI, GitHub, GitLab, Slack, Google, Stripe-live or Telegram credential in its fixed format. |
| `…::test_floor2_tracked_file_scan_fails_loudly_without_git[…]` | Git is missing, the tree is not a checkout, or `git ls-files` lists nothing, and the two committed-file checks do not fail. Until M31-S2 they silently scanned only `services/app`, which passed an AKIA sentinel committed under `docs/` in CI. |
| `…::test_floor2_no_env_file_tracked` | A `.env*` file other than a template is tracked. |
| `test_floor2_jwt_default_secret.py::test_floor2_default_jwt_secret_refused_whenever_login_is_on[saas\|self_hosted]` | Startup accepts the committed default `JWT_SECRET_KEY` while login is on, in SaaS or in `SELF_HOSTED` (an authenticated mode since SEC-05). Held by the SAFETY-027 VETO of SEC-05 `33c7d1d` as a strict `xfail`; `8356b15` keyed the refusal on `settings.single_user_mode`, the case XPASSed, and SAFETY-028 removed the marker. |
| `…::test_floor2_jwt_secret_check_controls` | A real key under `self_hosted` fails to start, or `SINGLE_USER_MODE` on loopback (anonymous caller is already the admin) is refused on the default key. |
| `test_floor2_test_fernet_key.py::test_floor2_multi_user_startup_refuses_the_committed_test_key` | 6b43cbb (SEC-06 follow-up). With `_running_under_pytest()` false, a multi-user lifespan starts on the all-zero `SETTINGS_ENCRYPTION_KEY` the root conftest commits. Per-user credentials encrypted with a key in the tree are readable from the tree. Mutation-checked (SAFETY-029): disabling the refusal fails here. The worker does not call `check_startup`; it only decrypts, and every write of a secret goes through the API, which refuses to start. |
| `…::test_floor2_committed_test_key_is_the_one_refused` | The key the root `conftest.py` sets differs from `secret_box.WELL_KNOWN_TEST_KEY`, so the tree would publish a key production accepts. |
| `…::test_floor2_pytest_signal_reads_nothing_an_operator_can_set` | `_running_under_pytest` reads anything but `sys.modules`: an env var, a setting or a file is a bypass a misconfigured `.env` can turn on. Mutation-checked: `or os.environ.get("TESTING") == "1"` fails here. |
| `…::test_floor2_no_runtime_module_imports_a_test_runner`, `…::test_floor2_runtime_import_graph_never_loads_a_test_runner` | A module under `app/` imports `pytest`/`_pytest` (statically, top level or lazy), or, in a fresh interpreter, importing every `app.*` module, `evals.runner` (the `cli evals` path) and the Celery default modules leaves `pytest` in `sys.modules`. Either makes the bypass signal true in production. pytest is installed in the runtime image (`requirements.txt`), so this is a property of the import graph, not the image. Ruled acceptable in SAFETY-029 on that basis; removing dev dependencies from the image is recommended as defence in depth, not required. Mutation-checked: a guarded `import pytest` in `app/core/cache.py` fails both. |
| `…::test_floor2_detect_secrets_baseline_is_wired_and_clean` | The pre-commit hook loses detect-secrets with `--baseline .secrets.baseline`, or loses `detect-private-key`. It also fails if a baseline entry is audited `is_secret: true`. |
| `…::test_floor2_sentinels_are_not_secret_shaped` | This tier's own sentinels would trip the scanner. |
| `…::test_floor2_host_credential_retry_failure_never_stores_or_logs_the_token` | GL#8: on the one host-credential retry, the re-read host OAuth token reaches `pipeline_runs.error_message`, a log, or the task's exception including its `__cause__` chain. |
| `…::test_floor2_host_credentials_are_never_handed_back_as_the_users_own` | A token refreshed during the host retry is exposed as `refreshed_credentials`, which classify, summarize and assets persist to the caller's `user_settings` (SAFETY-045). |
| `…::test_floor2_container_login_token_is_redacted_from_cli_failures` | The worker's own mounted `~/.claude` token appears unredacted in a CLI failure or its logs. |
| `…::test_floor2_host_credential_retry_is_not_logged_as_user_credentials` | The host retry logs `claude_code_using_user_credentials`, which attributes the operator's login to the user. |
| `…::test_floor2_expired_host_login_is_not_spent_and_never_leaks` | AI-049: a re-read host token whose `expiresAt` has passed still gets a second CLI call, or its token leaks into `pipeline_runs`, the logs or the cause chain. Mutation-checked: `_host_token_expired` forced to `False` turns it red on the call count. |
| `test_floor2_claude_login_mounts.py::test_floor2_only_the_ai_worker_pools_mount_a_claude_login` | R-025 (user ruling 2026-10-10): in any tracked `docker-compose*.yml`, a service outside `CLAUDE_LOGIN_SERVICES` (`worker`, `worker-ondemand` since GL#51, SAFETY-059) mounts something whose source or target names `claude`. Exact names: `worker-maintenance`, `api`, `beat`, `ui` and any new service fail. |
| `…::test_floor2_claude_mounts_come_only_from_the_dedicated_dir_read_only` | A Claude mount is not sourced from `${STUDYAIO_CLAUDE_LOGIN_DIR:-/opt/studyaio/claude-login}`, is writable, or lands anywhere except `/run/claude-host`, `/root/.claude/.credentials.json` or `/root/.claude/settings.json` (a directory overlay onto `/root/.claude` included). |
| `…::test_floor2_pinned_credentials_file_is_paired_with_the_tracking_dir_mount` | A service (per file, per service since SAFETY-059) mounts `.credentials.json` as a single file (which pins its inode, GL#8) without the `/run/claude-host` directory mount. Also fails if either AI pool's base `CLAUDE_HOST_CREDENTIALS_FILE` is not `/run/claude-host/.credentials.json`, or an overlay drops or repoints it (`environment: !override` included). |
| `…::test_floor2_no_compose_or_env_example_line_points_at_the_personal_claude_dir` | An uncommented line in a compose file or `.env.example` names `CLAUDE_CONFIG_DIR`, `~/.claude` or `$HOME/.claude`. |
| `…::test_floor2_setup_script_creates_a_private_empty_dir_and_copies_no_login` | `scripts/setup-claude-login.sh` (run for real with no token on stdin, via `setpriv` to uid 65534 when the suite runs as root) leaves the directory other than 0700, leaves `settings.json` other than a private `{}`, puts anything besides it and an optional private `{}` `.credentials.json` placeholder in the directory (SAFETY-053 allows the placeholder), or prints a planted personal token. |
| `…::test_floor2_setup_script_refuses_to_run_as_root` / `…has_its_root_guard_before_mkdir` | The script runs as root, or its refuse-root guard is missing or comes after `mkdir`. The behavioural variant runs only as root (CI). SAFETY-053 removed four assertions that followed `assert not target.exists()` and called `target.stat()`, which would have errored on every root run. Verified as root in the app image. |
| `test_floor2_claude_oauth_token.py::test_floor2_setup_token_reaches_the_cli_only_through_its_environment` | R-026 (user ruling 2026-10-10): the long-lived token from `CLAUDE_HOST_OAUTH_TOKEN_FILE` reaches the CLI anywhere other than `CLAUDE_CODE_OAUTH_TOKEN` in the child's env, or appears on argv, in the worker's own `os.environ` (during or after the call), or in a log. |
| `…::test_floor2_setup_token_echoed_on_auth_failure_never_stores_or_logs_and_is_not_retried` | The real classify task fails on a CLI 401 that quotes the token, and the token (or the configured `.credentials.json` fallback login) reaches `pipeline_runs.error_message`, a log, or the exception's cause chain. Also fails if the auth failure is retried. |
| `…::test_floor2_setup_token_echoed_on_any_failure_is_redacted` | A non-auth CLI failure that quotes the token raises an `AgentError` whose chain, or a log, contains it. |
| `…::test_floor2_per_user_credentials_win_over_the_setup_token` | A per-user-credential run is also handed the operator's token (env or temp config dir), the token surfaces in `refreshed_credentials`, or a per-user auth failure is retried on a host login. |
| `…::test_floor2_only_the_ai_worker_pools_are_told_where_the_setup_token_is` | A service outside `CLAUDE_LOGIN_SERVICES` in any tracked compose file sets `CLAUDE_HOST_OAUTH_TOKEN_FILE`, or an AI pool's value points outside `/run/claude-host/`. It also fails if base compose loses the variable on either AI pool, which would make the pin vacuous. |
| `…::test_floor2_no_compose_or_env_template_carries_the_token_value` | A live line in a compose file or `.env.example` sets `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_AUTH_TOKEN`. A token placed there would be readable through `docker inspect` or `.env`. |
| `…::test_floor2_worker_image_pins_the_claude_cli_version` | `services/app/Dockerfile` installs `@anthropic-ai/claude-code` without an exact `@x.y.z`. This CLI is the binary that receives the operator's token. |
| `…::test_floor2_setup_script_stores_the_token_private_and_never_prints_it` | The script, given the token on stdin, stores it as anything other than `oauth-token` 0600 in a 0700 dir. Also fails if it prints the token, leaves a `.oauth-token.*` temp file, lets a re-run without `--rotate` replace the token, or ignores `--rotate`. |
| `…::test_floor2_setup_script_refuses_the_personal_claude_dir` | Pointed at `$HOME/.claude`, the script exits 0, writes into that directory, or changes its mode. |
| `…::test_floor2_cli_runs_with_no_tools[setup_token\|per_user\|host_login]` | Green since SAFETY-053/057. `claude -p` runs without `--tools ""`. With its default read-only tools, which need no approval and are not confined to the cwd outside `--restricted`, a prompt-injected lecture can make it Read `/proc/self/environ`, `/run/claude-host/oauth-token` or `/root/.claude/.credentials.json`, then write the result into the summary the uploader reads. |
| `…::test_floor2_cli_environment_carries_no_worker_secret[…]` | Green since SAFETY-053/057. The CLI child's effective environment contains a planted worker secret (`JWT_SECRET_KEY`, `DATABASE_URL`, instance AI keys, Stripe, or an unlisted name, so a denylist cannot pass). `env=None` inherits everything and counts as a leak. Also fails if the fix drops the login the mode needs. |
| `…::test_floor2_sentry_event_for_a_cli_failure_carries_no_credential[…]` | Green since backend def2701 (SAFETY-053/057). A Sentry event, captured through the app's own `init_sentry` for a CLI failure, carries a worker secret, the setup token or a per-user token. The source is the frame locals of `_run_once`: `env` is not scrubbed, because the default scrubber is not recursive. Fix: `include_local_variables=False`. Simulated fixes on a scratch copy: ai's allowlist plus `--tools ""` turns the first two pins green, but this pin stays red on `[setup_token]`, because a short env dict fits within Sentry's 10-item window and so ships the token. Adding `include_local_variables=False` turns all three green. |
| `…::test_floor2_cli_environment_is_exactly_the_reviewed_allowlist[…]` | SAFETY-057. The CLI child's env holds any name outside `CHILD_ENV_ALLOWED` (`PATH`, `HOME`, `LANG`, `LC_ALL`, `CLAUDE_CONFIG_DIR`, `CLAUDE_CODE_OAUTH_TOKEN`), e.g. a password-bearing `REDIS_URL` added to the adapter's allowlist, which the sentinel pin cannot see because nobody planted it. Also fails if a non-token run gets `CLAUDE_CODE_OAUTH_TOKEN`. Widening the child env is a floor-2 review: edit `CHILD_ENV_ALLOWED`. |
| `…::test_floor2_sentry_is_initialised_without_frame_locals` | SAFETY-057. `init_sentry` does not pass `include_local_variables=False` (layer 1 alone; the end-to-end pin goes red only when both layers are gone). |
| `…::test_floor2_scrub_event_drops_frame_locals[exception\|threads]` | SAFETY-057. `scrub_event` leaves `vars` on an exception or thread frame (layer 2 alone). |

Mutation-checked in SAFETY-053, each mutant on a scratch git repo, all caught: token on argv; token in `os.environ`; token dropped from `_credential_values`; auth retry despite a token; per-user env also given the token; api told the token path; `CLAUDE_CODE_OAUTH_TOKEN=` in `.env.example`; unpinned CLI; script writing the token 0644; script echoing the token; script personal-dir guard removed; `--rotate` ignored.

Mutation-checked in SAFETY-057 (scratch copy of services/app, `scratchpad/muts_057.py`), all caught: `--tools ""` dropped; `--tools default`; `DATABASE_URL` / `REDIS_URL` / `SENTRY_DSN` added to the adapter allowlist (the last two only by the exact-allowlist pin); child env `{**os.environ}`; pre-fix `env=None` + `{**os.environ, …}`; operator token handed to every mode; `include_local_variables=False` and the frame-vars scrub removed together, and each alone.

### Claude login per worker pool (GL#51 queue split; devops `aec844a`, SAFETY-059)

`test_floor2_worker_pool_credentials.py` ties `CLAUDE_LOGIN_SERVICES` to the queue routing in
`app/worker.py` (`_QUEUE_TASKS`) through a static call graph (`_callgraph.py`: function-local
imports and package re-exports followed; `.s()`/`.delay()`/`.apply_async()` of a Celery task is
an enqueue, not an edge).

| Test | Fails when |
|---|---|
| `…::test_floor2_pool_guard_parses_routing_and_compose` | `_QUEUE_TASKS` is gone or names a non-task, or base compose loses one of the three pools. |
| `…::test_floor2_pool_call_graph_is_not_blind` | The graph stops seeing `get_agent` from any known AI task (classify, summarize, assets, courseops, targeted, concepts), `get_embedding_provider` from `reembed_user_chunks`, or recovery's function-local `resume_pipeline` import; or it starts treating `reembed_all_chunks`'s `.delay()` fan-out as a call. |
| `…::test_floor2_maintenance_tasks_never_reach_the_agent` | A task routed to `maintenance` reaches `get_agent`. `worker-maintenance` has no Claude login. |
| `…::test_floor2_claude_login_only_where_the_agent_is_called` | An allowlisted pool consumes no queue with an AI task (a login with no purpose), or a pool outside the allowlist consumes one (a worker without `-Q` counts as consuming every queue). |
| `…::test_floor2_an_ai_task_message_reaches_only_a_pool_with_the_login[send_task\|declared-address]` | A task that reaches `get_agent`, published on an in-memory broker either through `celery_app.send_task` or to its routed queue's declared exchange and routing key, is delivered to any other queue, or to a queue that a pool outside the allowlist consumes. The static pins above assume delivery follows the routing. Before AI-067 (`2bed33a`, R-044), bare `Queue(name)` shared one binding, so a message sent to an AI queue's declared address also reached `maintenance`. Added at the M33 gate. |

Revert-checked in SAFETY-059: the login dir mount plus `*claude-environment` added to
`worker-maintenance` (mount and token-path pins red); `worker-maintenance` added to the allowlist
(pool, parser and pairing pins red); `extract_concepts` routed to `maintenance` (both routing pins red).
Mutation-checked at the M33 gate: `app/worker.py` back to bare `Queue(name)` (the delivery pin red).

### Operator-only AI settings (SEC-01, SEC-03; backend `a5f3255`)

`claude_code_path` is the program the worker execs. Running a user's path runs their code next to the JWT secret, the DB URL and the instance keys, so it is held here.

| Test | Fails when |
|---|---|
| `test_floor2_operator_only_ai_settings.py::test_floor2_put_operator_only_ai_key_is_422_and_stores_nothing[…]` | `PUT /api/settings` naming `claude_code_path` or `claude_model` answers anything but 422, or stores anything. |
| `…::test_floor2_stored_legacy_path_and_model_never_reach_the_cli`, `…::test_floor2_get_user_ai_context_drops_stored_path_and_model`, `…::test_floor2_stored_legacy_model_never_reaches_the_anthropic_api` | A row stored before SEC-01 with a user path/model reaches the agent config, CLI argv[0], `--model`, or the Anthropic API adapter's model. |
| `…::test_floor2_factory_never_runs_a_user_supplied_executable_or_model` | `get_agent(user_settings={…"claude_code_path": X})` runs X. The factory is the single choke point every AI call passes; a second builder of that dict would otherwise reach the exec path again. Green since M32-S4-AI-025 (`045f85c`: the factory forwards neither key and the adapter has no `cli_path` override). Mutation-checked at the M32 gate: the factory setting the adapter's path from `user_settings["claude_code_path"]` fails here. |
| `…::test_floor2_get_settings_never_echoes_stored_path_or_model` | `GET /api/settings` returns a stored legacy path or model. |
| `…::test_floor2_self_hosted_user_endpoint_refuses_internal_targets[…]` | Self-hosted, a user base URL is accepted with a non-http(s) scheme, userinfo, a loopback/private/link-local/metadata/CGNAT/benchmark/multicast/broadcast/unspecified address, an IPv4-mapped, 6to4 or NAT64 wrapper of one, an IPv6 zone id, a decimal/octal/hex/short IPv4 spelling, fullwidth digits, a trailing-dot literal or name, `localhost`, a name with any private answer, an unresolvable name, or parser-confusion forms (`a@b`, `#@`, `\@`, bad port). |
| `…::test_floor2_self_hosted_user_endpoint_accepts_a_public_url[…]` | Control: a public URL is refused. |
| `…::test_floor2_hosted_user_endpoint_put_is_422_and_stores_nothing[…]` | Not self-hosted, a PUT of `zai_base_url`/`ollama_base_url` is accepted. |
| `…::test_floor2_stored_user_endpoint_is_revalidated_when_the_config_is_built[…]` | A stored URL reaches the agent config or public view when the deployment is hosted, or when its name now resolves inward (rebound since PUT). |
| `…::test_floor2_url_validator_checks_every_resolved_address_not_the_first` | One public answer hides a private one. |

Mutation-checked in SAFETY-026, all caught: `claude_code_path` back in `ALLOWED_KEYS` without the operator guard; `claude_code_path` / `claude_model` back in `_AGENT_CONFIG_KEYS`; public view iterating the operator-only keys; URL keys accepted when not self-hosted; stored URL not re-validated; only the first DNS answer checked; userinfo allowed. Two mutants survive by design, because a later layer catches the same input: removing the explicit v4-mapped unwrap (`ipaddress` already marks those non-global) and removing the numeric-spelling regex (the resolver turns them into a loopback literal that `_check_ip` refuses).

Use time (ai AI-024, `ee6b441`):

| Test | Fails when |
|---|---|
| `…::test_floor2_user_endpoint_rebound_after_config_is_refused_before_connecting[zai\|ollama]` | A user URL that passed at config time but now resolves inward reaches a constructed SDK client (no `AgentError` first). |
| `…::test_floor2_user_endpoint_clients_never_follow_redirects[zai\|ollama]` | The client built for a user URL follows redirects. |

Mutation-checked, all caught: the factory dropping `user_supplied_url` for zai and for ollama; `DefaultAsyncHttpxClient(follow_redirects=True)`; ollama `AsyncClient` without `follow_redirects=False`.

**Residual, logged on R-032, not a floor red:** no DNS pinning. The adapter validates, then httpx resolves again on connect, so a TTL-0 rebinding name can still answer public to the check and private to the connect. It is exposed only on self-hosted instances (hosted ones refuse user URLs), and SSRF is outside the four floors. Closing it needs a transport that connects to the validated address (ai).

### Claude CLI child isolation (AGENT-01, ai `ff90277`)

| Test | Fails when |
|---|---|
| `test_floor2_cli_child_isolation.py::test_floor1_cli_cwd_is_a_fresh_empty_private_dir_removed_after[…]` | The child inherits the worker's cwd (`/app`, every tenant's files), two calls share a cwd, the cwd is not empty or not 0700, or a `claude_*` dir survives the call. Both modes, with and without `CLAUDE_CLI_UID`. |
| `…::test_floor2_cli_runs_the_operator_binary_and_model_never_a_users[…]` | argv[0] or `--model` is not the operator's, or the caller's `model` argument appears on argv. |
| `…::test_floor2_cli_system_prompt_is_fixed_and_lecture_stays_off_argv[…]` | `--system-prompt` is not `_SYSTEM_PROMPT`, lecture text reaches argv, or `--tools ""` is not the last two argv items. |
| `…::test_floor2_cli_uid_mode_spawns_as_the_configured_uid_with_private_home` | With `CLAUDE_CLI_UID`, the child is not spawned as that uid/gid, its `HOME` is not its private cwd, or the cwd/config dir is not chowned to it. |
| `…::test_floor2_host_login_copy_is_never_handed_back_and_is_removed[…]`, `…::test_floor2_per_user_refresh_still_reaches_the_user_in_uid_mode` | The per-call copy of the operator login (from `CLAUDE_HOST_CREDENTIALS_FILE` or `~/.claude`) is read back into `refreshed_credentials` after a refresh, or its dir survives. Control: the user's own refresh still comes back. |
| `…::test_floor2_host_login_copy_token_is_redacted_from_cli_failures[…]` | Green since M32-S4-AI-025 (`045f85c`). The uid-mode copy built from `CLAUDE_HOST_CREDENTIALS_FILE` hands the child a token that is not in the adapter's redaction set (`_credential_values` covers `_host_credentials` only after a GL#8 retry, and the inode-pinned `~/.claude` file, which holds the pre-refresh token). A CLI failure quoting it would put the operator's token into the `AgentError`, so into `pipeline_runs.error_message` and the logs; fails if the copied login is not in the redaction set. |

Mutation-checked in SAFETY-026, all caught: cwd not passed; cwd not removed; `model or …` restored; `--system-prompt` dropped; a flag after `--tools ""`; host copy read back (`not host`/`credentials` guards removed); copy dir not removed; uid not passed to spawn.

Since SEC-006 (M34-S2) the pins above name their deployment through `conftest.py`: the uid mode runs on
`cli_root_worker` (euid pinned to 0, no opt-in: the AGENT-01 drop), every other spawn pin here, in
`test_floor2_claude_oauth_token.py`, `test_floor2_no_secrets.py` (GL#8 retry, container login, worker
provider errors) and `test_floor2_operator_only_ai_settings.py` runs on `cli_shared_uid_opt_in` (euid pinned
to 999, `CLAUDE_CLI_SHARED_UID_ACCEPTED=true`). Pinning the euid makes the tier mean the same as root (CI)
and as a developer. `test_floor2_sentry_event_for_a_cli_failure_carries_no_credential` also asserts the CLI was
spawned: a refusal is an `AgentError` with no credential and passed it vacuously.

### Non-root AI pools and the shared-uid refusal (SEC-006 option F; devops `fef057f`, ai `36ebc83`)

Review: `docs/gates/M34/sec006-safety.md` §5. Compose pins run over five stacks: `docker-compose.yml` alone and
merged with `prod`, `production`, `selfhosted`, and `selfhosted`+`production`, anchors and `<<` resolved,
`!reset`/`!override` honoured, `tmpfs` unioned as compose does (cross-checked against `docker compose config`).

| Test | Fails when |
|---|---|
| `test_floor2_cli_shared_uid_refusal.py::test_floor2_nonroot_multi_user_refuses_before_any_login_is_read_or_spawned[…]` | On a non-root, multi-user worker with no opt-in (unset, empty, `false`, `0`, `no`, `off`, any other word), for the setup token, the host login and per-user credentials: the CLI is spawned, a `oauth-token`/`.credentials.json` is opened, a temp dir is made or anything chowned, the error is not `ClaudeCliUnavailableError` or is transient, the refusal is not counted, a credential is in the error, its chain or the logs, or the message names no remedy. |
| `…::test_floor2_refusal_is_logged_once_and_counted_every_time` | `claude_cli_spawn_refused` is logged more than once per reason, carries a field beyond the reason, or a refusal is not counted. |
| `…::test_floor2_refusal_holds_through_get_agent[…]`, `…::test_floor2_refusal_fails_a_real_stage_once_without_a_retry_or_a_spawn` | The factory's instance or per-user `claude_code` adapter spawns; `classify` spawns, records more than one failed run, fails for another reason, or stores a credential. |
| `…::test_floor2_cli_uid_on_a_nonroot_worker_is_refused_in_every_mode[…]` | `CLAUDE_CLI_UID` on a non-root worker is not refused with the configuration error (with the opt-in, with `SINGLE_USER_MODE`, or both), or a temp dir/spawn happens first. |
| `…::test_floor2_operator_opt_in_spawns_at_the_worker_uid[…]`, `…::test_floor2_single_user_mode_spawns_without_the_opt_in[…]`, `…::test_floor2_root_worker_is_unchanged_without_the_opt_in[…]`, `…::test_floor2_root_worker_still_drops_to_the_cli_uid[…]` | Controls: the opt-in (`true`/`TRUE`/`1`/`yes`/` on `) or single-user mode does not spawn, a non-root spawn tries to drop, a root worker is refused, or a root worker with `CLAUDE_CLI_UID` does not drop to it with `extra_groups=[]` and a private `HOME`. |
| `…::test_floor2_every_cli_spawn_in_the_adapter_is_preceded_by_the_guard`, `…::test_floor2_refusal_error_is_a_plain_agent_error` | A function in `claude_code.py` that spawns does not call `ensure_claude_cli_spawnable()` as its first statement; the refusal error stops being a plain `AgentError`. |
| `test_floor2_worker_pools_nonroot.py::test_floor2_app_image_services_never_run_as_root[<stack>]`, `…::test_floor2_dockerfile_final_user_is_studyaio`, `…::test_floor2_image_user_uid_is_the_one_the_pins_assume` | A worker pool, `api` or `beat` has an effective `user` with uid or gid `0`/`root`, or none while the Dockerfile does not end `USER studyaio`; `studyaio` is not uid 999 (explicit `-u 999`, or the image's first `useradd -r`). |
| `…::test_floor2_no_app_image_service_configures_a_cli_uid_drop[<stack>]`, `…::test_floor2_cli_uid_is_not_set_in_env_example`, `…::test_floor2_shared_uid_opt_in_is_never_defaulted_on` | `CLAUDE_CLI_UID`/`GID` reach an app-image service or a live `.env.example` line; a compose file or `.env.example` sets `CLAUDE_CLI_SHARED_UID_ACCEPTED` to anything but empty, off or a pass-through defaulting off. |
| `…::test_floor2_ai_pool_home_is_a_private_tmpfs[<stack>]`, `…::test_floor2_home_detector_rejects[…]` | An AI pool's `HOME` is unset, `/`, `/root`, `/app`, under `/app/data`, `/run/claude-host`, `/root/.claude` or any mount, or has no tmpfs at exactly that path with the pool's uid and mode `0700`. |
| `…::test_floor2_login_scripts_never_suggest_a_widening_chmod`, `…::test_floor2_chmod_detector[…]` | `preflight-check.sh` or `setup-claude-login.sh` names a `chmod` that grants group/other or special bits, or a mode the detector cannot read. |
| `…::test_floor2_compose_merge_honours_reset_override_and_tmpfs_union`, `…::test_floor2_every_stack_has_the_app_image_services`, `…::test_floor2_nonroot_pin_catches_a_root_pool` | Guards the guard: the merge misreads `!reset`/`!override`/`tmpfs`, a stack loses a service, or a root pool passes. |

Mutation-checked in M34-S2 on a scratch copy, all red: the guard call deleted from `_run_once` (30 pins red);
the guard returning early for non-root; the `CLAUDE_CLI_UID` check moved after the opt-in; `user: "0:0"` on
`x-worker-common`; `user: root` on `worker-ondemand` in `prod.yml`; `CLAUDE_CLI_UID` back in `selfhosted.yml`;
the opt-in defaulted `true` in `prod.yml`; `HOME: /root`; the HOME tmpfs at `0755`; `chmod 750` in the
preflight hint; `USER root` appended to the Dockerfile.

### Metrics labels (M32 G3)

Both `/metrics` endpoints are unauthenticated: the worker's on `127.0.0.1:9101` and the
api's on `:8000`, reachable on the private network. Labels are also written to the worker's
multiprocess tmpfs. The policy is the one in `app/pipeline/metrics.py`.

| Test | Fails when |
|---|---|
| `test_floor2_metrics_labels.py::test_floor2_metric_label_names_are_the_allowed_enums` | A `prometheus_client` metric anywhere under `app/**` declares a label other than `stage`, `outcome` or `error_class`, or declares its labels non-literally. |
| `…::test_floor2_metric_label_values_are_never_identifiers_or_messages` | A `.labels(...)` call passes a positional value, an unlisted label, a value that is not a string literal or the local `stage`/`outcome`, or an `error_class` that is anything but `type(<x>).__name__` or, at a `CLASS_NAME_LOCAL_SITES` site only, a local bound from `<Class>.__name__` (so never `str(exc)` or an f-string with the message). |
| `…::test_floor2_api_instrumentator_keeps_route_templates` | `Instrumentator(...)` is given `should_group_untemplated=False` or opaque `**kwargs`. |
| `…::test_floor1_api_metrics_name_route_templates_not_raw_paths` | With the defaults `main.py` uses, a course code, an email or an unmatched raw path reaches the scrape, or the `handler` label is not the route template. This pins the library's behaviour across upgrades. |
| `…::test_floor2_reviewed_class_name_sites_are_not_stale`, `…::test_floor2_reviewed_class_name_site_detector[…]` | `CLASS_NAME_LOCAL_SITES` names a metric no longer labelled in that module; or the reviewed spelling (`error_class=<local>`) is accepted outside a listed site, when the local is bound from anything but `<Class>.__name__` of a class in the same module, when it is rebound, or when it is unbound. One site since SEC-006: `CLI_SPAWN_REFUSALS` in `agents/claude_code.py`. |
| `…::test_floor2_metric_policy_is_not_vacuous`, `…::test_floor2_label_*_detector[…]`, `…::test_floor2_instrumentator_detector[…]` | The checks stop seeing the worker metrics (8 or more, 10 or more `.labels` sites) or the api Instrumentator, or the detectors misjudge synthetic source. |

Mutation-checked in SAFETY-005, all red: a `user_id` label on `STAGE_FAILURES`; `error_class` carrying
`f"{type(exc).__name__}: {exc}"`; `STUCK_FAILED.labels(stage=artifact.id)`; `Instrumentator(should_group_untemplated=False)`.

### No email address in logs (SEC-08, GL#38; backend `40474fb`)

Addresses are personal data, not credentials, so this rides floor 2's "never logged" discipline
rather than its text. The call-site rule is the floor-grade layer; the redaction processor and
filter are a backstop.

| Test | Fails when |
|---|---|
| `test_floor2_no_email_in_logs.py::test_floor2_no_log_call_in_app_passes_an_email` | A log call in `app/**` (`debug`…`critical`, `fatal`, `msg`, `log`, `bind`, `new`, or `bind_contextvars`) passes an identifier ending in `email`/`emails`/`email_address`, a recipient name, a `["email"]` subscript or `.get("email")`, as a keyword, positional or inside an f-string. Wider than the backend's unit sweep, which matched four exact names. |
| `…::test_floor2_email_log_detector_is_red_on[…]`, `…::test_floor2_email_log_detector_accepts[…]` | The detector misses one of 13 violation shapes (incl. `email=user.email`) or flags `email_verified`/`email_sent`. |
| `…::test_floor2_redaction_runs_after_exc_formatting_and_right_before_the_renderer` | After `configure_logging`, `redact_emails` is missing, runs before `format_exc_info`, or anything but the renderer follows it. |
| `…::test_floor2_every_root_handler_has_the_email_filter` | A root handler present after `configure_logging` lacks `EmailRedactingFilter`. |
| `…::test_floor2_structlog_line_reaches_the_handler_without_an_address` | An address in a field, the event, a nested value, an `exc_info=True` traceback or a stdlib record reaches the handler stream. |
| `…::test_floor2_logger_exception_traceback_is_redacted` | Finding F1 (fixed `06c4fcb`, promoted SAFETY-040). `log.exception(...)` reaches stdlib `Logger.exception`, whose formatter appends a traceback after the message; it fails when `EmailRedactingFilter` stops rendering and scrubbing `exc_text` (and `stack_info`). Covers only handlers carrying the filter: a handler attached after `configure_logging` must add it itself. |
| `…::test_floor2_worker_configures_redacting_logging` | Finding F2 (fixed `344ce7e`, promoted SAFETY-040). `app/worker.py` no longer calls `configure_logging`. |
| `…::test_floor2_worker_setup_logging_signal_installs_the_filter` | Firing Celery's `setup_logging` signal (as worker and beat do at start) finds no receiver from `app.worker`, or leaves `redact_emails` out of structlog or a root handler without `EmailRedactingFilter`. Prefork children inherit the parent's configured root logger. |
| `…::test_floor2_profile_payload_hides_the_raw_consent_record` | The profile payload or its serialization schema exposes `ai_processing_consent_at`/`_version` (only `ai_consent_required` is public). |
| `…::test_floor2_usage_properties_cannot_carry_free_text`, `…::test_floor2_feedback_comment_never_reaches_a_log_or_usage_event`, `…::test_floor2_comment_leak_detector_is_red`, `…::test_floor2_feedback_comment_absent_from_events_and_logs` | Usage-event properties admit a free-text key or value, or an AI-feedback comment is passed to a log call or `usage_service.record` (statically, and through `PUT /api/feedback`). |

Mutation-checked in SAFETY-033, all red: `logger.info(..., email=user.email)` in `consent_service`;
`exclude=True` removed from the consent timestamp; the comment added to the usage properties.
Mutation-checked in SAFETY-040, all red: `app/core/logging.py` reverted to before `06c4fcb` (the F1 test);
`app/worker.py` reverted to before `344ce7e` (both worker tests); only the `@setup_logging.connect` decorator
removed (the signal test, which the AST check alone misses).

Outgoing mail (GL#53, `0be417c`, M33 gate). The text/plain alternative repeats every link as a
visible URL, so reset, verification and invite tokens appear twice in each message.

| Test | Fails when |
|---|---|
| `test_floor2_email_delivery_logs.py::test_floor2_sent_mail_logs_no_address_token_or_body[…]` | Sending a reset, verification or invite mail through the real logging configuration (DEBUG) puts the recipient address, the link token or the body into the handler stream. Not vacuous: the token must be in both MIME alternatives and `email_sent` must be logged. |
| `…::test_floor2_failed_mail_logs_no_address_or_token[…]` | An SMTP failure (a recipients-refused error, or any exception whose text names the recipient) leaves the address or the token in the `email_send_failed` line or its traceback. |

## 3. AI only via the adapter (amended by ADR 0003 and ADR 0005)

> every AI call goes through a sanctioned gateway, either AgentAdapter obtained via
> `get_agent`, or, for embeddings, EmbeddingProvider obtained via
> `get_embedding_provider`; outside `app/agents/**` and `app/pipeline/**` (the
> Celery worker), each gateway is called only at the call sites enumerated in ADR
> 0003 (`get_agent`) and ADR 0005 (`get_embedding_provider`), and a new such call
> site requires amending the ADR that lists it

The first six are the checks from ADR 0003's Consequences section, in its order.
The rest are ADR 0005's "What safety adds", items 1 to 7.

| Test | Fails when |
|---|---|
| `test_floor3_ai_via_adapter.py::test_floor3_request_time_get_agent_sites_equal_adr_0003_allowlist` | The set of `(module, enclosing function)` pairs that call `get_agent` outside `agents/` and `pipeline/` is not exactly `REQUEST_TIME_GET_AGENT_CALL_SITES`. Either direction fails: a site missing from the list, or a listed site that is gone. |
| `…::test_floor3_no_provider_sdk_import_outside_agents` | `anthropic`, `openai`, `ollama` or (ADR 0005) `sentence_transformers` is imported outside `app/agents/**`. That includes imports inside a function and `importlib` imports. |
| `…::test_floor3_no_adapter_class_reference_outside_agents` | An adapter class name is used outside `app/agents/**` as a name, an attribute, an import, or an exact string. Docstrings and comments do not count. |
| `…::test_floor3_no_claude_cli_spawn_outside_agents` | A subprocess or exec call outside `app/agents/**` has `claude` or `claude_code_path` as its program. |
| `…::test_floor3_pipeline_get_agent_only_in_celery_task_modules` | A `get_agent` call under `app/pipeline/` is in a module that registers no Celery task. |
| `…::test_floor3_detectors_are_not_vacuous` | The collectors stop finding the known pipeline call sites and SDK imports. |
| `…::test_floor3_get_embedding_provider_sites_equal_adr_0005_allowlist` | The `(module, enclosing function)` pairs that reference `get_embedding_provider` outside `agents/` and `pipeline/` are not exactly `GET_EMBEDDING_PROVIDER_CALL_SITES`, in either direction. A reference counts, not only a call (`Depends(get_embedding_provider)` reaches the gateway too), and import aliases are followed. |
| `…::test_floor3_embed_texts_sites_equal_adr_0005_allowlist` | The pairs that reference `.embed_texts` (attribute, or the string, for a `getattr`) outside `agents/` and `pipeline/` are not exactly `EMBED_TEXTS_CALL_SITES` (five, ADR 0005 as amended 2026-10-16: `index_service.embed_artifact_chunks` replaced `index_artifact_chunks`). |
| `…::test_floor3_aembed_texts_sites_equal_adr_0005_allowlist` | The pairs that reference the agents-side async wrapper `aembed_texts` (name, attribute or string) outside `agents/` and `pipeline/` are not exactly `AEMBED_TEXTS_CALL_SITES` (one: `index_service.aembed_artifact_chunks`, ADR 0005 amendment 2026-10-16). It counts because its own `provider.embed_texts` sits in `agents/`, out of scan, so its callers are where the embedding happens. Mutation-checked: an `aembed_texts` call added to `chat_service` fails here. |
| `…::test_floor3_startup_embedding_sites_never_embed` | `main.py:warn_if_embedding_provider_unavailable`, the startup probe, calls `embed_texts`. |
| `…::test_floor3_injected_provider_sites_have_only_worker_callers` | A function in `INJECTED_PROVIDER_CALLERS` that embeds with a provider it is handed (`index_service.embed_artifact_chunks`, `aembed_artifact_chunks`, and the wrapper `index_artifact_chunks`) is referenced from a caller not listed for it, or is no longer defined (a rename would pass vacuously), or lists a caller that is neither under `pipeline/` nor itself pinned, or `pipeline/index.py:_index` reaches none of them. Subset, not equality: a caller going away is safe, so the stage moving from the wrapper to `aembed_artifact_chunks` needs no edit here. |
| `…::test_floor3_pipeline_get_embedding_provider_only_in_celery_task_modules` | A `get_embedding_provider` reference under `app/pipeline/` is in a module that registers no Celery task. |
| `…::test_floor3_no_embedding_backend_reference_outside_agents` | `SentenceTransformerProvider`, `OpenAIEmbeddingProvider`, `OllamaEmbeddingProvider` or `reset_embedding_provider` is referenced outside `app/agents/**` as a name, attribute, import or exact string (docstrings and comments do not count), or a class there subclasses `EmbeddingProvider`. |
| `…::test_floor3_embedding_detectors_are_not_vacuous` | The collectors stop finding `pipeline/index.py:_index`, the `openai`, `sentence_transformers` and `ollama` imports in `agents/embeddings.py`, or `qa.ask_question`'s `embed_texts`. It also fails if a banned name is no longer defined in `agents/embeddings.py`, so a rename cannot leave the ban guarding nothing. |

The embedding checks were each shown red on an injected violation in a scratch copy
(M31-S2-SAFETY-021): a new request-side factory call, an aliased factory, a removed
listed site, a new `embed_texts`, a `getattr` string, the startup probe embedding, a
request-side caller of `index_artifact_chunks` (since M34: of `embed_artifact_chunks` or `aembed_artifact_chunks`, and a new request-side `aembed_texts`), a factory call in a non-task pipeline
module, a `sentence_transformers` import, a backend class, `reset_embedding_provider`,
an `EmbeddingProvider` subclass, and the worker site removed.

### Request-time AI spend is quota-checked and metered as the caller (M32 G1; backend `421dfa9`)

Pinned in M33-S1-SAFETY-005. Gate condition G1 (`docs/gates/M32/floors.md` N-1):
`POST /api/settings/test-ai` spent the instance provider with no quota, ceiling,
metering or rate limit. The pin rides the ADR 0003 list, so a new site cannot join
it unmetered. The caller-identity half is floor-1 wiring.

| Test | Fails when |
|---|---|
| `test_floor3_request_time_ai_quota.py::test_floor3_every_adr_0003_site_has_a_pinned_route` | `SPEND_ROUTES` (site to route handlers) does not cover exactly `REQUEST_TIME_GET_AGENT_CALL_SITES`. |
| `…::test_floor3_service_site_routes_are_exactly_the_pinned_ones[<site>]` | A service site (`chat_service.send_message`/`stream_message`, `concept_service.extract_and_save_concepts`) gains or loses a caller outside its own module, `app/pipeline/` and `app/agents/` (import aliases followed). An extra request-time caller would be unchecked. |
| `…::test_floor3_instance_ai_spend_is_quota_checked_for_the_caller[<site>-<route>]` | The route handler has no `check_ai_quota(session, <caller>.id, …)` (caller = the `Depends(get_current_user[_or_default])` parameter) before the line where it reaches `get_agent` or the site function, run unconditionally or behind only "the caller's loaded agent config `is None`" (the instance provider), with no `try`, loop, closure or other guard around it. |
| `…::test_floor3_instance_ai_spend_is_recorded_against_the_caller[<site>-<route>]` | No `record_ai_call(session, <caller>.id, …)` in the handler, and the site function does not record on a `user_id` that the handler fills with `<caller>.id`. |
| `…::test_floor3_test_ai_on_instance_checks_then_meters_the_caller[ok\|provider-error]` | Through the app, as a non-default free-tier caller on the instance provider: the order is not check, `get_agent`, record; or the check or the record names anyone but the caller (or the tier is not theirs). Covers the failed call too. |
| `…::test_floor3_test_ai_refused_by_the_ceiling_never_builds_an_agent` | A `GlobalCeilingError` refusal is not a 429, or an agent is built or a call recorded anyway. |
| `…::test_floor3_own_provider_config_never_builds_the_instance_agent` | A non-`None` config from `_agent_config_from_overrides` with no credential is built into an adapter instead of `ProviderCredentialError`. This is what makes test-ai's `metered = cfg is None` sound: an own-provider config can never fall back to the operator's key. |
| `…::test_floor3_quota_detector_*`, `…::test_floor3_metering_detector[…]`, `…::test_floor3_route_derivation_is_not_vacuous` | On synthetic source, the detectors accept a missing check, another user's id, a literal id, a check after the spend, a swallowed check, an unrelated, inverted, reassigned or `else` guard, a guard on a config that is not the caller's, or a record for someone else, or reject the two accepted shapes. |

Mutation-checked in SAFETY-005 on a scratch copy, all red: test-ai without `check_ai_quota` (4 tests);
the check for the default admin's id (3); both `record_ai_call`s removed (3); recorded for another id (3);
`if not metered` (4); chat send without its check (1); `concept_service` recording on `course_id` (1);
qa's check inside `try/except: pass` (1); the factory falling back to the instance on an own config with
no key (1).

### AI-processing consent precedes every AI spend (SEC-08, GL#38; backend `40474fb`, `275bc9f`)

A floor-adjacent guard under floor 3: lecture content leaves the instance when a provider is
called. The route set is **derived**: every live route whose handler reaches a call to
`check_ai_quota`, `get_agent`, `resume_pipeline`, `run_pipeline`, `.apply_async` or `.delay`,
directly or through a function in `app/api`, `app/services` or `app/core` (import aliases and
same-module helpers followed). 14 routes today: the backend's 13 at GL#38 plus `POST /api/weak-spots/targeted` (ADR 0007, SAFETY-024 at M33-S2), which it reaches through `_enqueue_targeted` → `.delay()`.

| Test | Fails when |
|---|---|
| `test_floor3_ai_consent_gate.py::test_floor3_every_ai_route_requires_consent` | A derived route lacks `require_ai_consent` in its dependency tree. `CONSENT_EXEMPT` (empty) is the only way out, with a reason. |
| `…::test_floor3_consent_route_derivation_is_not_vacuous`, `…::test_floor3_consent_resolver_follows_imports_and_helpers`, `…::test_floor3_consent_exemptions_are_live` | The resolver stops reaching any of the 14 known AI routes (`KNOWN_GATED`), misses a direct, helper, imported-name or module-alias path on synthetic source, or an exemption is stale. |
| `…::test_floor3_unconsented_caller_is_refused_before_any_sink` | Any derived route answers an unconsented caller with anything but `403 ai_consent_required`, or a sink (every `get_agent`/`run_pipeline`/`resume_pipeline`/`check_ai_quota` bound in an `app.*` module, and Celery `Task.apply_async`/`delay`) is reached. |
| `…::test_floor3_outdated_consent_version_is_refused` | A consent recorded to older disclosure wording passes. |
| `…::test_floor3_consent_has_no_role_tier_or_self_hosted_bypass[…]`, `…::test_floor3_single_user_mode_is_the_only_consent_bypass` | Outside single-user mode a role (admin, demo), tier or `self_hosted` exempts an unconsented user, `consent_required` gains a second early branch, or `require_ai_consent` gains a branch. |
| `…::test_floor3_consent_error_is_not_swallowed_in_app` | Code in `app/` catches `AiConsentRequiredError` or `AuthorizationError` without re-raising (the login throttle re-raises). |

Mutation-checked in SAFETY-033: removing `dependencies=[Depends(require_ai_consent)]` from
`POST /api/qa/ask` turns four tests red.

### Fixed replies are not metered, and only they (GL#35)

| Test | Fails when |
|---|---|
| `test_floor1_retrieval_followup.py::test_floor3_ai_called_matches_whether_the_agent_was_built[…]` | Send and stream, below and above the relevance floor: `ai_called` disagrees with whether `get_agent` was called. |
| `…::test_floor3_ai_called_flag_is_tied_to_the_agent_branch[…]`, `…::test_floor3_ai_flag_detector_is_red_on[…]` | In `chat_service`, `ai_called` is not exactly `plan.reply is None`, is assigned twice, `plan.reply` is written after it, or `get_agent` is reachable outside the `plan.reply is None` branch. |
| `…::test_floor3_chat_api_skips_metering_only_on_an_explicit_false` | `api/chat.py` skips `record_ai_call` on anything but an explicit `ai_called is False` (send) or a stream event carrying `ai_called: False`. |

Mutation-checked in SAFETY-033: `ai_called = False` in `send_message` turns two tests red. GL#35 adds
no `get_agent` or embedding call site: the ADR 0003 and ADR 0005 allowlist tests stay exact. Its new
counter `studyaio_retrieval_below_floor_total` declares only the `stage` label, which the metrics-label
pin accepts.

## 4. User data is never lost (amended by ADR 0004)

> nothing deletes uploads or generated content under data/ except explicit account
> deletion and the explicit user-initiated deletes of the user's own items
> enumerated in ADR 0004, and dedup/re-summarize/asset regeneration never destroys
> prior versions or study history

| Test | Fails when |
|---|---|
| `test_floor4_user_data_never_lost.py::test_floor4_every_blob_delete_is_classified` | A storage `delete`/`delete_prefix`, `unlink`, `os.remove` or `shutil.rmtree` under `app/` is not listed in `BLOB_SANCTIONED`, `BLOB_PENDING_RULING` or `BLOB_VIOLATIONS`. It also fails if a sanctioned or pending site no longer exists. A violation that has been fixed away is not called stale, so the code fix can land without editing this tier. |
| `…::test_floor4_every_content_row_delete_is_classified` | The same check for DB deletes of uploaded or generated-content models (`summary_versions` included), and for every `session.delete`. |
| `…::test_floor4_no_delete_site_awaits_a_ruling` | `BLOB_PENDING_RULING` or `DB_PENDING_RULING` is not empty. Empty since the 2026-10-04 rulings. |
| `…::test_floor4_no_violation_site_remains` | A site in `DB_VIOLATIONS` or `BLOB_VIOLATIONS` is still in the code. Empty since M31-S2-BACKEND-019 archived instead of deleting (`asset_service.save_flashcards`/`save_quiz_questions`, unlisted in SAFETY-025). |
| `…::test_floor4_user_item_allowlist_is_exactly_adr_0004` | The sanctioned sites that cite ADR 0004 are not exactly `USER_ITEM_DB_DELETE_SITES` and `USER_ITEM_BLOB_DELETE_SITES` (ADR 0004 Decision 3, verbatim), or one of them is gone from the code. |
| `…::test_floor4_course_delete_is_bounded_to_adr_0004_item_1` | `course_service.delete_course` deletes a model not in `COURSE_DELETE_MODELS` (ADR 0004 #1 "What goes"), gains a `.delete()` call (a blob or `session.delete`), or stops deleting a listed model. The inventory is keyed on the function, so without this a sanctioned `delete_course` would wave through any new delete. `SummaryVersion` is listed as part of the course's summaries (BACKEND-019); ADR 0004 #1 should name it verbatim. This is condition 3, "bounded". |
| `…::test_floor4_user_item_deletes_reachable_only_from_their_routes` | A sanctioned user-item delete (`delete_course`, `merge_courses`, `_discard_summary`, `delete_course_document`, `delete_deadline`, `delete_session`) is referenced from anywhere but the callers listed in `USER_ITEM_DELETE_CALLERS`. This is ADR 0004 condition 1, "explicit". Callers are matched by name, so a same-named function elsewhere fails here instead of hiding a caller. |
| `…::test_floor4_account_purge_reachable_only_from_account_deletion` | `purge_user_storage` or `delete_user_account` gains a caller outside account deletion. |
| `…::test_floor4_lecture_upload_dedup_writes_and_deletes_nothing` | A duplicate lecture upload stores, deletes or dispatches anything. |
| `…::test_floor4_reference_checked_delete_has_only_classified_callers` | `_delete_blob_if_unreferenced` gains a caller not in `REFERENCE_CHECKED_DELETE_CALLERS`, or `discard_failed_upload_blob` is called from anywhere but the two courseops upload routes. The shared `store.delete` site serves the single-document delete (ADR 0004 #2) and the failed-upload cleanup, both sanctioned for different reasons, so its callers are pinned. |
| `…::test_floor4_duplicate_course_document_upload_keeps_original_blob` | Re-uploading the same course document deletes the blob the existing document's row points at. The fake session answers the reference count from real rows, so cleanup that skips the count fails. Fixed in M31-S1-BACKEND-008 (`a2cd687`). |
| `…::test_floor4_failed_assessment_attach_keeps_existing_blob` | A 404 on attach deletes a blob that an existing document uses (same fake). Fixed in `a2cd687`. |
| `…::test_floor4_failed_upload_never_deletes_another_users_blob` | User B's failed upload of user A's exact file deletes A's blob, or `discard_failed_upload_blob` deletes a key outside the caller's own `courseops/<user_id>/` prefix. |
| `…::test_floor4_resummarize_increments_version` | Re-summarizing a course and week does not increment `version`. |
| `…::test_floor4_resummarize_preserves_prior_version` | After a re-summarize, there is no `summary_versions` row (handed to `session.add`/`add_all`, or an `INSERT`) carrying version 1's text and version number, or that row's `file_path` no longer holds version 1's bytes. The caller has already written version 2 to the key it hands the service, as the summarize stage does, so a snapshot pointing at that key fails. Green since M31-S2-BACKEND-019. |
| `…::test_floor4_merge_keep_source_snapshots_target_summary` | Merge with `on_conflict=keep_source` overwrites the target summary without a `summary_versions` row carrying the target's prior text and version, writes that row only after the overwrite, or leaves the row pointing at a key that no longer holds the prior bytes. A control checks that `keep_source` actually ran. This is ADR 0004 § Amendment 2026-10-04: the overwritten target is not merge-discard. Green since M31-S2-BACKEND-019. |
| `…::test_floor4_merge_carries_moved_summarys_versions_to_target` | Merge moves a week summarized only in the source to the target, but that summary's `summary_versions` rows stay keyed to the archived source, where a later sanctioned course delete (ADR 0004 #1) destroys them. Re-homing by `UPDATE` or by mutating loaded rows both count. It also fails if the re-home collides with the target's own `(course_id, week, version)` (a blanket move of every source version does, on a `keep_source` conflict week). Controls check that the week moved and that `keep_source` ran. Found in SAFETY-025; green since M31-S2-BACKEND-026 re-homed the moved week's versions. |
| `…::test_floor4_asset_regeneration_keeps_study_history` | Regeneration issues a `DELETE` on `flashcards` or `quiz_questions` that is not conditioned on `flashcard_reviews` or `quiz_attempts`. A control checks that new items were saved. Green since M31-S2-BACKEND-019. |
| `…::test_floor4_account_deletion_purges_every_summary_blob_of_the_user` | After `delete_user_account`, any summary or summary-version blob of the deleted user remains anywhere under the storage root (found by content, not by key). The scenario runs the real calls over `_minidb.MiniDB`, a table set that answers statements like a database, and a real local storage root: the summarize stage's writes and a re-summarize for a live course, a course later deleted, and a merge source whose moved week carries its retained v1 to the target; then `merge_courses`, `delete_course` on the archived source and on the other course, then account deletion. It also fails if deleting a course destroys a blob that still belongs to a live course (a version merge re-homed), or if account deletion destroys another user's summaries. R-020 (M31 re-run F-3, M32 condition C5). Green since M32-S1-BACKEND-005 (`a3ab6ce`, deleted-course ledger); SAFETY-009 mutation-checked it red with the ledger sweep removed and with the marker write removed. |
| `…::test_floor4_account_purge_spares_other_users_deleted_course_blobs` | Deleting one account destroys another user's summaries, including the retained blobs of a course that user deleted. Both users delete a course, so both have ledger markers; a ledger read across users (an unkeyed `ledger/deleted-courses` prefix) fails here, which the R-020 pin cannot see. |
| `…::test_floor4_account_purge_ignores_ledger_entries_that_name_no_course` | A ledger listing entry whose last segment is not a course id widens the summary sweep. On S3, `list_objects_v2` returns zero-byte folder placeholders (`ledger/deleted-courses/<user_id>/`); the purge turns the empty segment into `summaries/` and deletes every user's summaries. Simulated over a local root by appending those keys to `list_keys`. Green since `d719eaf` (BACKEND-006): the purge sweeps only a segment that fully matches the UUID shape. SAFETY-013 mutation-checked it red with the check removed. Not in this tier: a failed listing now keeps the ledger (S3 `list_keys` raises instead of returning `[]`), so the deleted-course blobs stay attributable for a retry; `tests/unit/services/test_account_purge_deleted_courses.py::test_purge_keeps_ledger_when_listing_fails` holds it and was mutation-checked red. |

The account-deletion pin was run in a scratch copy against four fixes. Green: the
purge also deletes every `file_path` in the user's `summaries` and
`summary_versions` rows, and `delete_course` deletes the blobs of the rows it
deletes. Red: the path sweep alone (the deleted course survives), `delete_course`
sweeping its whole `summaries/<course_id>` prefix (destroys a version merge
re-homed to the live target), and the purge sweeping all of `summaries/`
(destroys the other user's). A fix that deletes blobs in `delete_course` also
needs ADR 0004 #1 amended and `COURSE_DELETE_MODELS` and the blob inventory
updated by `safety`; keying summaries per user does not.

Blob inventory after BACKEND-005 (SAFETY-009). The fix chose the ledger over
both shapes above (decisions.md 2026-10-08 C5) and adds no delete site:

- `ledger/deleted-courses/<user_id>/<course_id>` is a zero-byte marker that
  `course_service.delete_course` writes with `store.put` before it deletes the
  rows. It is a write to a fresh key under a prefix nothing else uses. It
  overwrites no user content, and `_authorize_path` does not serve it
  (`_VALID_PREFIXES` is `extractions`, `summaries`). `delete_course` still has no
  `.delete()` call, so `test_floor4_course_delete_is_bounded_to_adr_0004_item_1`
  holds unchanged.
- Only the sanctioned `purge_user_storage` `store.delete_prefix` site deletes
  under `ledger/`. It sweeps `summaries/<id>` for each marker, then the user's
  ledger prefix last.
- `StorageBackend.list_keys` is read-only on both backends: Local uses
  `rglob` with a root-escape guard, S3 uses `list_objects_v2`. It is not a
  delete primitive, and the inventory scanner finds no delete in it.
- Uploaded file names cannot forge a marker. `sanitize_filename` strips `/`, so
  no upload or courseops key can leave its `uploads/<id>_` or
  `courseops/<user_id>/` parent.
- Course ids are `generate_id()` UUID7 primary keys, unique across users, so a
  marker names exactly one user's course. They are fixed-length, so a
  slash-less S3 prefix cannot match a longer id.

The three retention pins were run in a scratch copy against a fix shaped like
BACKEND-019: a snapshot row plus the prior blob under a versioned key, and
`archived_at` instead of `DELETE`. With that fix, all of them go green. Three
wrong fixes each stay red: a snapshot pointing at the overwritten key, a merge
snapshot written after the overwrite, and regeneration that saves nothing.

## R-023: per-user time zone (ADR 0006), across floors

`test_r023_clock_zone.py`, M32-S2-SAFETY-037. The zone in `user_settings.timezone` is
user-supplied and unverified, so each floor is checked against it.

| Test | Fails when |
|---|---|
| `test_r023_quota_and_usage_modules_never_read_the_user_zone` | A module that touches `UsageRecord`, or `quota_service`/`core/quota.py`, names `user_today`, `user_now`, `local_day_end_utc`, `get_user_timezone`, `get_user_tz`, a `.timezone` attribute or a `tz`/`timezone` parameter. ADR 0006 Decision 6: the quota day is UTC so that changing zone cannot buy a fresh daily allowance on the instance's credentials. |
| `…::test_r023_usage_day_is_utc_whatever_the_zone[...]` | With the clock frozen where `Pacific/Kiritimati` and `Etc/GMT+12` are on different dates, `get_usage_today`, `get_global_usage_today` or `record_usage` compares or writes a `record_date` other than the UTC date. Mutation-checked: `get_usage_today` on the Kiritimati day fails here and in the structural test. Since SAFETY-026 the write side is read from either `session.add(UsageRecord)` or an executed `INSERT` (GL#19 upsert) and must be exactly one `(caller, UTC date)` row, with the upsert bounded by `uq_usage_user_date`. Mutation-checked: upsert for another user, on the Kiritimati date, or conflicting on `record_date` alone all fail. |
| `…::test_r023_zone_change_touches_no_usage_record` | Setting the zone touches `usage_records` or adds a row. |
| `…::test_r023_valid_timezone_refuses_hostile_keys_without_raising[...]` | `valid_timezone` raises or accepts a path-like, host-specific, NUL, surrogate, oversized, non-ASCII or non-string key. Green since BACKEND-039 (SAFETY-040 lifted the SAFETY-037 veto): `localtime` used to be accepted on Debian hosts because `available_timezones()` walks the host's TZPATH and `/usr/share/zoneinfo/localtime -> /etc/localtime`. |
| `…::test_r023_accepted_zone_keys_come_from_the_declared_tzdata_only` | `valid_timezone` accepts a key that is not in the `tzdata` package's `zones` list, so the key set depends on the host or base image. Green since the same fix. |
| `…::test_r023_every_valid_key_fits_the_column` | A shipped key is longer than `user_settings.timezone`'s `String(64)`. |
| `…::test_r023_bad_stored_zone_degrades_to_utc[...]` | `user_now`, `user_today` or `local_day_end_utc` raises on, or does not answer in UTC for, a bad stored value. **RED on `localtime`**, which resolves to the host's zone. |
| `…::test_r023_listed_but_unloadable_zone_degrades_to_utc[...]` | A key that passes validation but fails to load (`ZoneInfoNotFoundError`, `ValueError` on a corrupt TZif, `OSError`) raises out of `user_now`/`user_today` instead of falling back to UTC. Green since BACKEND-039 (`clock._zone` guards `ZoneInfo(...)`): ADR 0006 Decision 4 says a bad zone never raises in a request or a beat task. |
| `…::test_r023_put_hostile_zone_is_422_and_stores_nothing[...]` | `PUT /api/settings` answers a hostile `timezone` with anything but 422, or writes it to the row. **RED on `localtime`.** |
| `…::test_r023_zone_lookup_filters_on_the_caller` | `get_user_timezone` runs a `user_settings` statement not filtered on the caller's `user_id`. Mutation-checked: dropping the `where` fails here. |
| `…::test_r023_get_user_tz_takes_identity_only_from_authentication` | `deps.get_user_tz` gains a parameter that is not a `Depends`, stops depending on `get_current_user_or_default`, or passes anything but `user.id` to the lookup. |
| `…::test_r023_zone_route_ignores_a_smuggled_user` | A zone route given `user_id`/`tz`/`timezone` query parameters naming someone else looks up, or serves, anyone but the caller. |
| `…::test_r023_zone_is_carried_only_by_the_callers_own_settings` | A Pydantic model under `app/api/` other than `SettingsResponse`/`SettingsUpdateRequest` has a `timezone` or `tz` field (a leaderboard or admin view leaking zones). |
| `…::test_r023_zone_column_read_only_through_the_scoped_lookup` | Code outside `settings_service` (and the model) reads a `.timezone` attribute, i.e. reaches the column without the scoped lookup, beyond the exact expressions and counts classified in `ZONE_ATTRIBUTE_BEAT_READS` (SAFETY-040: AI-036's hourly beat jobs in `app/pipeline/notification_tasks.py`, 3x `UserSettings.timezone`, 1x `row.timezone`). One more read of the same expression fails too. Mutation-checked. |
| `…::test_r023_beat_zone_reads_are_worker_only` | A classified beat read lives outside `app/pipeline/`, or a module outside `app/pipeline/` and `app/worker.py` imports it (a route could then run a cross-user zone query). Mutation-checked: importing `notification_tasks` from `app/api/settings.py` fails here. |
| `…::test_r023_beat_zone_is_joined_to_the_rows_own_owner` | A beat `select` of `UserSettings.timezone` does not join `UserSettings` on `UserSettings.user_id == <Owner>.user_id` with `<Owner>.user_id` in the same select, or `user_settings.user_id` loses `unique`; i.e. user A's zone could be applied to user B's sends. Mutation-checked: a cross join, a join on `Deadline.course_id`, and a join on an owner the select does not carry all fail here. |
| `…::test_r023_beat_send_claim_is_per_user_and_zone_degrades_to_utc` | The Redis send-claim key `notif-sent:{kind}:{user}:{local_date}` collides across users or kinds, or `_is_send_time`/`_local_day_start_utc` raises on, or does not treat as UTC, a hostile stored zone. Mutation-checked: dropping `{user_id}` from the key fails here. |

Floor 4 needs nothing new: the R-023 diff (`28fe02e..bc63f39`) adds no delete, unlink or
overwrite of user data, and a zone change is not retroactive (ADR 0006 Decision 4).

## SEC-10: credential-surface throttles, beside the floors

`test_sec10_auth_rate_limit.py`, M33-S1-SAFETY-050. Not one of the four floors, but held in this tier because a
silent weakening is invisible to every other test: the per-address limiter on `/api/auth/*` and the per-account
login throttle. The limiter's `memory://` clock is replaced (`limits.storage.memory.time`), so runner latency
cannot move a request across a window.

| Test | Fails when |
|---|---|
| `test_sec10_every_limiter_counts_with_a_moving_window` | `RATE_LIMIT_STRATEGY` is not `moving-window`, or the module limiter, or `build_limiter` on `memory://` or `redis://`, is not a `MovingWindowRateLimiter`. Mutation-checked: the constant set to `fixed-window`, and the factory's `strategy=` kwarg forced to `fixed-window`, both fail here. |
| `…::test_sec10_no_limiter_is_built_outside_the_factory` | Any `Limiter(...)`/`_OutagePolicyLimiter(...)` call in `app/**` other than the one in `build_limiter`; a second limiter could pick its own strategy and outage policy. |
| `…::test_sec10_window_boundary_does_not_refill_the_login_budget` | One login at t0, four at t0+59.9, then five at t0+60.1: anything but `401` for the first six and `429` for the last four, or any 60 s span letting more than five through. A fixed window answers ten `401`s inside 0.2 s. Mutation-checked with both fixed-window mutations above. |
| `…::test_sec10_auth_limiter_store_down_fails_closed` | With the limiter's Redis unreachable, `POST /api/auth/login` answers anything but 503, or the password check runs. Mutation-checked: `FAIL_CLOSED_PREFIXES` not matching `/api/auth/` fails here. |
| `…::test_sec10_no_auth_limit_is_loosened_or_dropped` | A credential route in `app/api/auth.py` loses its `@limiter.limit`, carries a non-literal limit, or a limit looser than its M32 ceiling (`AUTH_LIMIT_CEILINGS`: login and OAuth MFA 5/min, demo login 10/min, the rest 3/min). Mutation-checked: login at `10/minute` fails here. `…::test_sec10_ceiling_check_reads_lambda_and_literal_limits` is its control. |
| `…::test_sec10_unit_fake_implements_every_call_the_throttle_makes` | `login_throttle` calls a `redis_client` method that the unit suite's `FakeRedis` (`tests/unit/conftest.py`) does not implement. Without it the throttle raises, logs `login_throttle_unavailable` and fails open in every unit test, as it did before `b1e20d9`. |
| `…::test_sec10_login_throttle_counts_and_engages_under_the_unit_fake`, `…::test_sec10_failed_logins_over_http_engage_the_throttle` | Under that same fake, `record_failure` does not count 1, 2, … , `login_throttle_unavailable` is logged, `login_throttle_engaged` is not, or (over HTTP, spaced past the per-address limit) the login after the free allowance is not delayed. Mutation-checked: removing `FakeRedis.incr` fails all three throttle tests. |

## Weak-spot engine: targeted generation (ADR 0007, GL#45), floors 1, 3, 4

M33-S2-SAFETY-024. `POST /api/weak-spots/targeted` writes a `targeted_generations` row and
enqueues `app.pipeline.targeted_task.generate_targeted_items` with the row id only. Two worker
functions read that table without a `user_id` predicate and are classified in
`UNSCOPED_FUNCTION_ALLOWED`: `_claim` (it holds only the id; everything after acts as
`row.user_id`) and `_recover_stuck` (cross-user beat job, one UPDATE to `failed`/`timeout`).
The tests below pin what those entries rest on. All behavioural ones run over MiniDB with two
users whose courses share a code and week.

| Test | Fails when |
|---|---|
| `test_floor1_targeted_generation.py::test_floor1_targeted_task_inserts_only_into_the_row_owners_course` | For A's row: an item lands outside A's course/artifact; any of B's items changes; B's stems reach the prompt's `avoid`/`missed`/`topics` (dedup against another user); AI context or usage is resolved for anyone but A; or any statement on an owned table other than the single `FOR UPDATE` claim by id is not filtered on A. |
| `…::test_floor1_targeted_task_never_generates_into_another_users_course` | A row owned by A that names B's course produces any item, reaches `get_agent`, or ends other than `failed`/`no_source`. |
| `…::test_floor1_targeted_task_takes_the_row_id_only` | The task or `_run` gains a parameter (a payload owner). |
| `…::test_floor1_targeted_unscoped_functions_are_worker_only` | `_claim`, `_recover_stuck` or `recover_stuck_generations` is imported, called or named (non-docstring string) outside `targeted_task.py` and `worker.py`. |
| `…::test_floor4_recovered_row_gets_no_items_inserted_later` | A row recovered to `failed`/`timeout` while the model ran gets items inserted, or loses recovery's verdict. Runs on `_IdentityMapSession` (identity map, `expire_on_commit=False`, `populate_existing` honoured, dirty-only flush): recovery changes the database row while the worker holds its stale `running` copy from `_claim`. It was red at M33-S2 because `_persist`'s `FOR UPDATE` re-select returned that stale copy (found by `qa`, `tests/integration/test_targeted_worker.py`). M33-S2-AI-053 added `.execution_options(populate_existing=True)` to the `_persist` and `_claim` re-selects; this pin was a strict `xfail` until then. |
| `…::test_floor4_stuck_generation_recovery_only_fails_rows` | Recovery runs anything but one UPDATE on `targeted_generations` setting exactly `status`, `error_code`, `completed_at`, or `_recover_stuck` calls a delete/remove primitive. |
| `…::test_floor4_regeneration_never_archives_targeted_items` | `asset_service.save_flashcards`/`save_quiz_questions` (pipeline regeneration) archives an `origin='targeted'` item, removes any item, or stops archiving the pipeline ones (control). |
| `…::test_floor1_daily_cap_counts_the_callers_rows_in_the_utc_day` | The cap of 6 ignores a row at exactly UTC midnight, counts another user's rows, counts rows from before UTC midnight (a rolling 24 h window), or the AI quota is checked when capped. |
| `…::test_floor3_targeted_spend_path_order` | A foreign course is not a 404 for a capped caller, or reaches the quota; an in-flight job is not returned ahead of the cap; another user's in-flight row (even naming the caller's course) is returned to the caller; or a quota refusal leaves a row. |

Mutation-checked in a scratch copy (`scratchpad/mut24/mutate.py`) on the AI-053 code, 17 mutants, all caught (the 17th removes `populate_existing` from `_persist`):
`_course_stmt`, `_artifacts_stmt`, `_existing_stmt` (dedup) or the `_persist` lock unscoped;
all three source lookups unscoped together (behavioural: B's course gets items); AI context
resolved for another id; `_persist` without the `status == "running"` re-check; the
`origin == "pipeline"` filter dropped from either regeneration archive; the cap count unscoped,
made a rolling 24 h, or the quota moved before it; `_find_in_flight` unscoped; the route's
`require_ai_consent` removed (two floor-3 tests); recovery writing an extra column; the
recovery task name used in `app/api/`.

## Coverage

The floor tier is mostly static: it reads all of `app/**` but executes very little
of it, so a percentage of `app` is the wrong measure. Measure the tier's own guard
code, so that no detector branch goes dead:

```
pytest tests/safety --cov=tests/safety --cov-fail-under=95
```

The handoff for M31-S1-SAFETY-003 has the numbers and the proposal for a second
coverage measure: the floor-enforcing modules under unit and floor tiers together.

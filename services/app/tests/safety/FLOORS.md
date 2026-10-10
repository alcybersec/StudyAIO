# Floor tier — floor to test map

The floor tier is `services/app/tests/safety/`, owned by `safety`. Every test runs
without Postgres, Redis or Docker: AST checks over `app/**`, FastAPI's test client
with dependency overrides, and mock sessions that record the SQL a handler builds.

Floors are quoted from `docs/strategy.md` §6. A floor is **green** only when every
test listed for it passes. A floor question that only the user can decide is held
in a `*_PENDING_RULING` dict, and a test per floor is red while that dict is not
empty. The 2026-10-04 rulings emptied every one of them, and no `xfail` is left in
the tier. A test marked **RED until** names the task whose code change it waits on.

Run:

```
cd services/app && .venv/bin/python -m pytest tests/safety -v
```

## 1. Tenant isolation

> an authenticated endpoint never returns or mutates another user's rows; every
> user-owned query filters on user_id

| Test | Fails when |
|---|---|
| `test_floor1_tenant_isolation.py::test_floor1_route_sweep_every_owned_query_filters_on_caller` | Any authenticated, non-admin route (every method), called with a type-valid request that carries a foreign value in every path parameter and every JSON body field (`_payload.py` builds it from the route's own types), runs a statement on a user-owned table that does not compare `user_id` to the caller's id. It also fails if `session.get()` is called on an owned model. It also fails if the sweep reaches fewer than 60 routes that query an owned table (74 at the M31 gate), because below that the check proves nothing. Green since M31-S2-BACKEND-013 fixed R-015 (`qa/ask`, `study/review`, `study/quiz-attempt`, `study/timed-plan`, `gamification/achievements/mark-notified`). |
| `…::test_floor1_route_sweep_owned_parent_never_unlocks_foreign_rows` | Same sweep, but every lookup that is scoped to the caller finds a row the caller owns, so handlers get past their ownership check. Fails when a later statement on an owned table is keyed on request input alone: it binds a planted value that no caller-scoped primary-key lookup has vetted, binds no id of the caller's own row, and has no `user_id` filter. A course *code* is never vetted, because it is unique per user, not globally. Green since BACKEND-013 (R-015: `GET /courses/{code}/weeks/{n}`, plus the five routes above). |
| `…::test_floor1_route_sweep_reaches_every_handler` | A swept route is still rejected by FastAPI's request validation (a 422 with a field-error list), so its handler never runs and the sweep cannot see it. Only the multipart upload routes in `SWEEP_UNREACHED_BY_DESIGN` may be. It also fails if a listed route starts reaching its handler. |
| `…::test_floor1_payload_builder_plants_type_valid_foreign_values` | The request builder (`_payload.py`) stops producing a body that validates for a declared type (bounds, enums, literals, dates, UUIDs, nested models, a model-level "one of" rule), or stops planting a recognisable foreign value. The sweep is only as wide as this builder. |
| `…::test_floor1_every_table_is_classified` | A table is neither user-owned (it has `user_id`, a FK to an owned table, or is polymorphic) nor listed in `UNOWNED_TABLES`. |
| `…::test_floor1_no_unscoped_session_get_on_owned_model` | An `api/` or `services/` function calls `session.get(OwnedModel, <its own parameter>)` and the call is not classified. It also fails on a stale classification. SAFETY-013 removed `_get_course_owned` (its `user_id=None` branch went in BACKEND-006) and mutation-checked that restoring the branch fails here. |
| `…::test_floor1_no_unscoped_query_function_outside_classification` | A `services/` or `pipeline/` function builds a query on a user-owned model, takes no caller parameter (`user_id`, `user`, …) that it uses, and puts no `<Model>.user_id` predicate or `filter_by(user_id=)` in it, and the function is not in `UNSCOPED_FUNCTION_ALLOWED` with a reason (worker-only, webhook, token lookup, FK traversal from a scoped parent). It also fails on a stale entry. This reaches code no route sweep can. Green since BACKEND-013 and AI-014 (R-015: `classify._get_known_courses`, `achievement_service.mark_notified`, `summary_service.get_summary_for_week`, `timed_session_service.generate_timed_plan`). SAFETY-024 classified `_owner._row_owner_async` (R-022: worker-only owner lookup for the SSE channel; returns an id, fails closed). |
| `…::test_floor1_unscoped_query_detector_is_not_vacuous` | The detector stops seeing two known worker-side unscoped reads. |
| `…::test_floor1_unscoped_query_detector_needs_a_predicate_not_a_mention` | On synthetic source, the detector counts a join on `Model.user_id` (`UserXP.user_id == User.id`) or a selected `Course.user_id` as a `user_id` predicate, or flags a real `== value`/`.in_()` predicate. Closed SAFETY-021 blind spot 2 in SAFETY-025; that surfaced `snapshot_summary`, `notify_admins` and `backfill_courseops_storage_keys`, all classified. |
| `…::test_floor1_caller_parameter_is_never_optional` | A `services/` or `pipeline/` function uses a caller parameter (`user_id`, `user`, …) that defaults to `None`, or puts a `user_id` filter behind a `None`/truthiness check on it (`if user_id is not None: query = query.where(...)`), and is not in `OPTIONAL_CALLER_ALLOWED` with a reason. Such a function is scoped only when its caller remembers to pass the identity; the route sweep pins today's route callers, but a worker, CLI or service caller that omits it reads or writes every user's rows. R-021 (M31 re-run F-4, M32 condition C6). Green since M32-S1-BACKEND-006 (`d1276a0`: 71 functions at `d37528f` made keyword-only required with unconditional filters) and M32-S1-AI-012 (`8812e4a`: `classify._get_or_create_course` takes a required owner and raises on `""`). SAFETY-009 classified ten pipeline functions under the C6 ruling (the six artifact stages and the concepts task act for `artifact.user_id`; `_ingest` fails closed on the NOT NULL users FK; the two orchestrator dispatchers run no query). SAFETY-013 mutation-checked it red with `get_review_item` back to `user_id: str \| None = None`, with `get_course_document`'s filter behind `if user_id:`, and with `_get_or_create_course` back to `if user_id:`. It also fails on a stale entry. |
| `…::test_floor1_row_owner_stages_never_use_a_bare_optional_caller` | A stage classified `_ROW_OWNER` in `OPTIONAL_CALLER_ALLOWED` reads `user_id` anywhere other than inside a `warn_on_owner_mismatch(...)` call. The allowlist is keyed on the function, so without this a later edit that hands the possibly-`None` payload owner to a scoped service would pass, and so would one that lets the payload override the row again (`user_id or artifact.user_id`), which spends B's credentials and billing on A's artifact. Tightened in SAFETY-013 after AI-012 (`8812e4a`) made the row win. Mutation-checked: `_get_known_courses(session, user_id)` in `_classify` and `owner_id = user_id or artifact.user_id` in `_summarize` both fail here. |
| `…::test_floor1_optional_caller_detector_is_not_vacuous` | On synthetic source, the R-021 detector stops flagging a `None` default (positional or keyword-only), a filter skipped on `if user_id:`, or a function that forwards a `None`-defaulted caller, or starts flagging a required caller, a fail-closed `if user_id is None: raise`, or an unused caller parameter. |
| `…::test_floor1_caller_filter_detector_rejects_widened_predicates` | `_tenant.filters_on_user` reads `user_id = :caller OR …`, `NOT (user_id = :caller)`, `user_id != :caller` or `user_id IN (:caller, :victim)` as caller-scoped, or stops accepting `= :caller`, `IN (:caller)` or an OR whose every branch is caller-scoped. Closed SAFETY-021 blind spot 1 in SAFETY-025; every sweep test runs on this helper. |
| `…::test_floor1_pipeline_only_fetch_is_pipeline_only` | The one allowlisted worker-only unscoped fetch gains a caller outside `app/pipeline/`. |
| `…::test_floor1_cannot_attach_document_to_another_users_assessment` | `attach_assessment_document` lets user B attach a document to user A's assessment. The fake session answers like a database: only a lookup filtered on the caller's `user_id` comes back empty, so an unscoped `select` fails too, and a control call as the owner must find the row. Fixed in M31-S1-BACKEND-008 (`a2cd687`). |
| `…::test_floor1_no_cross_user_route_awaits_a_ruling` | `SWEEP_PENDING_RULING` is not empty: some route reads across users and the user has not ruled on it. Empty since the 2026-10-04 rulings; the leaderboard moved to `SWEEP_OPT_IN_CROSS_USER`. |
| `…::test_floor1_leaderboard_lists_only_opted_in_users` | `GET /api/gamification/leaderboard` runs a `user_xp` statement that, evaluated row by row (`_predicate.admits`), keeps another user who opted out or has no `user_settings` row, or drops one who opted in. The caller's own row is unconstrained. It also fails if the route runs no `user_xp` query, or uses SQL the evaluator does not model. The leaderboard is exempt from the sweep (`SWEEP_OPT_IN_CROSS_USER`) because the sweep asks whether `user_id` is compared to the caller, which cannot judge an opt-in filter. Ruled 2026-10-04 (R-007): opt-in, hidden by default. Green since M31-S2-BACKEND-019 (`leaderboard_opt_in`). |
| `…::test_floor1_predicate_evaluator_models_sql_semantics` | `_predicate.admits` stops keeping exactly the rows Postgres would: three-valued logic, outer joins that null the unmatched side, IN over lists and subqueries. It also fails if an unmodelled construct stops raising `Unreadable`. |
| `test_floor1_owner_routing.py::test_floor1_pipeline_events_publish_to_a_resolved_owner` | A pipeline `publish_pipeline_event[_sync]` call names a recipient that is not a local assigned only from `resolve_event_owner(...)` (the artifact-row owner lookup), or a pipeline event is published outside `app/pipeline/`. The R-022 bug (publishing to the Celery payload `user_id`) fails here. Green since M32-S1-AI-021 (`1d08ef4`). |
| `…::test_floor1_payload_user_never_receives_another_owners_stage_event[<stage>]` | For classify/extract/summarize/index/assets, with the row owned by A and the payload naming B, any outcome (completed, waiting_review, non-retry error, retry) publishes to B's channel. |
| `…::test_floor1_unknown_row_owner_drops_stage_events[<stage>]` | A missing row makes a stage publish to anyone (it must pass `None`, which the publisher drops) instead of guessing the payload user. |
| `…::test_floor1_ingest_with_precreated_row_never_reaches_payload_user[<outcome>]`, `…::test_floor1_ingest_without_row_uses_payload_user_only_before_the_row_exists` | Ingest with a pre-created artifact (every upload) reaches the payload user for a row owned by another, or guesses on an unknown row; or, with no pre-created row, the placeholder (`pending`/`unknown`) events stop going to the payload user (who creates and so owns the row) or the result event for the row the run produced is not re-resolved from that row. Ruled acceptable in SAFETY-024: the pre-row events carry only a placeholder id and the payload user's own file. |
| `…::test_floor1_event_owner_lookup_fails_closed`, `…::test_floor1_publisher_drops_an_ownerless_event`, `…::test_floor1_row_owner_lookup_is_worker_only` | `resolve_event_owner` falls back to the payload owner on a miss or error, the publisher opens a channel for a `None` owner, or the unscoped `_row_owner[_async]` lookup (classified in `UNSCOPED_FUNCTION_ALLOWED`) gains a caller outside `app/pipeline/`. |
| `…::test_floor1_chat_unowned_course_code_is_indistinguishable_from_missing[<msg>]` | A course code typed into chat (GL#10, BACKEND-019) that another user owns yields a different plan (reply text, quiz action, scope) or a different number of statements than a code nobody owns, i.e. chat becomes an existence oracle for other users' course codes. The fake session finds the row for any lookup not filtered on the asking non-owner, so a dropped filter is visible; the control (owner) must resolve it. Mutation-checked in SAFETY-024: unscoping `get_course_by_code`, or branching a miss on an unscoped probe, both fail. |
| `…::test_floor1_chat_sources_come_only_from_caller_scoped_chunks` | Stored chat sources name a chunk or artifact outside the caller-scoped `search_chunks` result, e.g. from the adapter's own citation list (model output). |
| `test_floor1_owner_routing.py::test_floor1_chat_carried_foreign_course_is_indistinguishable_from_missing[…]` | GL#31 (backend `423b178`). A course code another user owns, named in an earlier turn, carries scope into a follow-up, or yields a different plan or statement count than a code nobody owns. Control: the owner's code is carried. |
| `…::test_floor1_chat_bare_week_lists_only_the_callers_courses[…]` | "Which course for Week N" names, or scopes to, another user's course, or differs from an empty database for a non-owner. |
| `…::test_floor1_chat_scope_carry_adds_no_ai_call_site` | `_carry_scope`, `_courses_with_week` or `_plan_message` calls an adapter (the clarifying reply is a template). |

Mutation-checked in SAFETY-026, all caught: carried code looked up unscoped; week listing with no owner filter; week listing filter OR-widened. An extra unscoped probe whose result is not used survives, correctly: output and statement count stay equal, so it discloses nothing.

| Test | Fails when |
|---|---|
| `test_floor1_study_nudge.py::test_floor1_nudge_candidate_subqueries_are_each_correlated_to_the_candidate` | PROD-03 (GL#15, backend `ebae1cb`). An EXISTS sub-query in `nudge_service.candidates_stmt` (opt-in, studied, reviewed, uploads) lacks `<table>.user_id = users.id` as a plain AND conjunct, so another user's rows decide who is nudged. A correlation under OR also fails. |
| `…::test_floor1_nudge_selection_returns_ids_not_other_users_data` | The cross-user selection returns a column other than `users.id` and booleans (an email, a zone, content). |
| `…::test_floor1_nudge_selection_is_worker_only` | A module outside `app/pipeline/`, `app/worker.py` and `nudge_service` itself imports `nudge_service` or names `find_nudge_candidates`/`candidates_stmt`. |
| `…::test_floor1_nudge_delivery_is_keyed_on_the_candidate_only[…]` | `send_study_nudge` writes an inbox row for anyone but the candidate, or runs a statement on an owned table (or `users`) not filtered on the candidate. |
| `…::test_floor1_preference_seeding_writes_and_reads_only_the_new_users_rows`, `…::test_floor1_signup_seeds_preferences_for_the_user_just_created[…]` | Default-preference seeding creates or looks up rows for anyone but the new user, or one of the three signup paths (`register_user`, `create_or_link_oauth`, admin `create_user`) seeds for anything but `user.id` of the row it just created. |
| `…::test_floor2_email_unsubscribe_link_is_static_and_carries_no_token_or_pii[<sender>]` | Any `email_service.send_*` email lacks the footer unsubscribe link, or the link is anything but the static `<app_base_url>/settings/notifications` (no token, address or id; a signed one-click link would be a credential in every inbox and mail log). |

Mutation-checked in SAFETY-026 (scratch copy, `scratchpad/mutate.py`), all caught: `studied` uncorrelated; opt-in correlation OR-widened; `User.email` selected; a route importing `find_nudge_candidates`; seeding for another owner; inbox row to another user; unsubscribe URL carrying the recipient.

The deeper layers live in other tiers: `tests/integration/test_idor_row_level.py`
runs against a real database, and `tests/unit/api/test_endpoint_scoping_guard.py`
plus `test_idor_scoping.py` cover endpoint wiring.

## 2. No secrets in the tree

> no plaintext credentials, tokens or keys committed, and per-user AI credentials
> are never logged or returned by the API

| Test | Fails when |
|---|---|
| `test_floor2_no_secrets.py::test_floor2_settings_get_never_returns_a_stored_credential` | `GET /api/settings` contains any stored per-user credential. |
| `…::test_floor2_settings_put_never_echoes_a_credential` | The `PUT /api/settings` response echoes one back. |
| `…::test_floor2_settings_schemas_carry_no_credential_value` | `SettingsResponse` gains a credential-valued field, or `SettingsUpdateRequest` gains a credential input that is not in `SECRET_KEYS`. |
| `…::test_floor2_account_export_never_returns_a_stored_credential` | `GET /api/auth/account/export` returns any stored credential from `user_settings.settings_json`, including the token nested in `claude_cli_credentials`. Fixed in M31-S1-BACKEND-008 (`b5f57e6`). |
| `…::test_floor2_provider_error_never_echoes_a_stored_credential[<site>]` | A provider error that quotes every stored credential (the nested CLI token too) reaches the response, a structlog event or a stdlib log record at a request-time AI call site: `POST /api/settings/test-ai`, `POST /api/qa/ask`, `chat_service.send_message`, `chat_service.stream_message`, `POST /api/concepts/extract/{artifact_id}`. It also fails if no provider was called. The first four are green (R-008: `7eecbac` for test-ai, `718faa0` for qa and chat). The concepts site (ADR 0003 #5) runs the real adapter against a provider SDK that echoes the key it was sent (`_ProviderEcho`). Green since M31-S2-AI-014 (redaction at `AgentError` construction, R-012) and BACKEND-013 (the concepts route catches `AgentError`). |
| `…::test_floor2_worker_provider_error_never_stores_or_logs_a_credential[<site>-<backend>]` | Run eagerly as Celery tasks, `classify_artifact` and `process_course_document` hit a provider that echoes the key, for each of `anthropic_api`, `openai`, `zai` and `claude_code` (CLI stdout echoing the OAuth token). Fails if the credential reaches `pipeline_runs.error_message`, a structlog event, a stdlib log record (Celery's own `raised unexpected` line included) or the exception the task ends with. Green since AI-014 (R-012; before it, classify stored the key in `pipeline_runs.error_message` and courseops logged it as `courseops_document_failed`). |
| `…::test_floor2_global_handler_never_returns_or_logs_raw_agent_error[<path>]` | An `AgentError` (a subclass of it, built outside the adapter so it carries raw text) that reaches `main.studyaio_error_handler` leaves the provider's text, the instance key or any per-user key in the response, a structlog event or a stdlib log record. Two paths: a direct call to the handler, and a probe route mounted for the test that lets the error escape, so FastAPI's own dispatch chooses the handler. Until M32-S1-SAFETY-004 this drove `POST /api/concepts/extract`, which BACKEND-013 made catch `AgentError` itself; from then on the test never reached the handler, and disabling the handler's `AgentError` branch left it green (M31 re-run mutant 3c, F-1). Now shown red on three handler mutants: the branch disabled, the branch narrowed to `type(exc) is AgentError`, and the branch logging `str(exc)`. |
| `…::test_floor2_credentials_never_logged` | A stored credential appears in a structlog event or a stdlib log record during save, rejected save, or adapter construction for any backend. It also fails if one appears in a 422 body. |
| `…::test_floor2_no_high_confidence_secret_in_tracked_files` | A tracked file contains a private key block, or an AWS, Anthropic, OpenAI, GitHub, GitLab, Slack, Google, Stripe-live or Telegram credential in its fixed format. |
| `…::test_floor2_tracked_file_scan_fails_loudly_without_git[…]` | Git is missing, the tree is not a checkout, or `git ls-files` lists nothing, and the two committed-file checks do not fail. Until M31-S2 they silently scanned only `services/app`, which passed an AKIA sentinel committed under `docs/` in CI (pipeline 525, job 4301). |
| `…::test_floor2_no_env_file_tracked` | A `.env*` file other than a template is tracked. |
| `…::test_floor2_detect_secrets_baseline_is_wired_and_clean` | The pre-commit hook loses detect-secrets with `--baseline .secrets.baseline`, or loses `detect-private-key`. It also fails if a baseline entry is audited `is_secret: true`. |
| `…::test_floor2_sentinels_are_not_secret_shaped` | This tier's own sentinels would trip the scanner. |
| `…::test_floor2_host_credential_retry_failure_never_stores_or_logs_the_token` | GL#8: on the one host-credential retry, the re-read host OAuth token reaches `pipeline_runs.error_message`, a log, or the task's exception including its `__cause__` chain. |
| `…::test_floor2_host_credentials_are_never_handed_back_as_the_users_own` | A token refreshed during the host retry is exposed as `refreshed_credentials`, which classify, summarize and assets persist to the caller's `user_settings` (SAFETY-045). |
| `…::test_floor2_container_login_token_is_redacted_from_cli_failures` | The worker's own mounted `~/.claude` token appears unredacted in a CLI failure or its logs. |
| `…::test_floor2_host_credential_retry_is_not_logged_as_user_credentials` | The host retry logs `claude_code_using_user_credentials`, which attributes the operator's login to the user. |
| `…::test_floor2_expired_host_login_is_not_spent_and_never_leaks` | AI-049: a re-read host token whose `expiresAt` has passed still gets a second CLI call, or its token leaks into `pipeline_runs`, the logs or the cause chain. Mutation-checked: `_host_token_expired` forced to `False` turns it red on the call count. |
| `test_floor2_claude_login_mounts.py::test_floor2_only_the_worker_mounts_a_claude_login` | R-025 (user ruling 2026-10-10): in any tracked `docker-compose*.yml`, a service other than `worker` mounts something whose source or target names `claude`. |
| `…::test_floor2_claude_mounts_come_only_from_the_dedicated_dir_read_only` | A Claude mount is not sourced from `${STUDYAIO_CLAUDE_LOGIN_DIR:-/opt/studyaio/claude-login}`, is writable, or lands anywhere except `/run/claude-host`, `/root/.claude/.credentials.json` or `/root/.claude/settings.json` (a directory overlay onto `/root/.claude` included). |
| `…::test_floor2_pinned_credentials_file_is_paired_with_the_tracking_dir_mount` | A file mounts `.credentials.json` as a single file (which pins its inode, GL#8) without the `/run/claude-host` directory mount. Also fails if base `CLAUDE_HOST_CREDENTIALS_FILE` is not `/run/claude-host/.credentials.json`, or an overlay drops or repoints it (`environment: !override` included). |
| `…::test_floor2_no_compose_or_env_example_line_points_at_the_personal_claude_dir` | An uncommented line in a compose file or `.env.example` names `CLAUDE_CONFIG_DIR`, `~/.claude` or `$HOME/.claude`. |
| `…::test_floor2_setup_script_creates_a_private_empty_dir_and_copies_no_login` | `scripts/setup-claude-login.sh` (run for real with no token on stdin, via `setpriv` to uid 65534 when the suite runs as root) leaves the directory other than 0700, leaves `settings.json` other than a private `{}`, puts anything besides it and an optional private `{}` `.credentials.json` placeholder in the directory (SAFETY-053 allows the placeholder), or prints a planted personal token. |
| `…::test_floor2_setup_script_refuses_to_run_as_root` / `…has_its_root_guard_before_mkdir` | The script runs as root, or its refuse-root guard is missing or comes after `mkdir`. The behavioural variant runs only as root (CI). SAFETY-053 removed four assertions that followed `assert not target.exists()` and called `target.stat()`, which would have errored on every root run. Verified as root in the app image. |
| `test_floor2_claude_oauth_token.py::test_floor2_setup_token_reaches_the_cli_only_through_its_environment` | R-026 (user ruling 2026-10-10): the long-lived token from `CLAUDE_HOST_OAUTH_TOKEN_FILE` reaches the CLI anywhere other than `CLAUDE_CODE_OAUTH_TOKEN` in the child's env, or appears on argv, in the worker's own `os.environ` (during or after the call), or in a log. |
| `…::test_floor2_setup_token_echoed_on_auth_failure_never_stores_or_logs_and_is_not_retried` | The real classify task fails on a CLI 401 that quotes the token, and the token (or the configured `.credentials.json` fallback login) reaches `pipeline_runs.error_message`, a log, or the exception's cause chain. Also fails if the auth failure is retried. |
| `…::test_floor2_setup_token_echoed_on_any_failure_is_redacted` | A non-auth CLI failure that quotes the token raises an `AgentError` whose chain, or a log, contains it. |
| `…::test_floor2_per_user_credentials_win_over_the_setup_token` | A per-user-credential run is also handed the operator's token (env or temp config dir), the token surfaces in `refreshed_credentials`, or a per-user auth failure is retried on a host login. |
| `…::test_floor2_only_the_worker_is_told_where_the_setup_token_is` | A non-worker service in any tracked compose file sets `CLAUDE_HOST_OAUTH_TOKEN_FILE`, or the worker's value points outside `/run/claude-host/`. It also fails if base compose loses the variable, which would make the pin vacuous. |
| `…::test_floor2_no_compose_or_env_template_carries_the_token_value` | A live line in a compose file or `.env.example` sets `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_AUTH_TOKEN`. A token placed there would be readable through `docker inspect` or `.env`. |
| `…::test_floor2_worker_image_pins_the_claude_cli_version` | `services/app/Dockerfile` installs `@anthropic-ai/claude-code` without an exact `@x.y.z`. This CLI is the binary that receives the operator's token. |
| `…::test_floor2_setup_script_stores_the_token_private_and_never_prints_it` | The script, given the token on stdin, stores it as anything other than `oauth-token` 0600 in a 0700 dir. Also fails if it prints the token, leaves a `.oauth-token.*` temp file, lets a re-run without `--rotate` replace the token, or ignores `--rotate`. |
| `…::test_floor2_setup_script_refuses_the_personal_claude_dir` | Pointed at `$HOME/.claude`, the script exits 0, writes into that directory, or changes its mode. |
| `…::test_floor2_cli_runs_with_no_tools[setup_token\|per_user\|host_login]` | Green since ai 31c1f28 (SAFETY-053/057). `claude -p` runs without `--tools ""`. With its default read-only tools, which need no approval and are not confined to the cwd outside `--restricted`, a prompt-injected lecture can make it Read `/proc/self/environ`, `/run/claude-host/oauth-token` or `/root/.claude/.credentials.json`, then write the result into the summary the uploader reads. |
| `…::test_floor2_cli_environment_carries_no_worker_secret[…]` | Green since ai 31c1f28 (SAFETY-053/057). The CLI child's effective environment contains a planted worker secret (`JWT_SECRET_KEY`, `DATABASE_URL`, instance AI keys, Stripe, or an unlisted name, so a denylist cannot pass). `env=None` inherits everything and counts as a leak. Also fails if the fix drops the login the mode needs. |
| `…::test_floor2_sentry_event_for_a_cli_failure_carries_no_credential[…]` | Green since backend def2701 (SAFETY-053/057). A Sentry event, captured through the app's own `init_sentry` for a CLI failure, carries a worker secret, the setup token or a per-user token. The source is the frame locals of `_run_once`: `env` is not scrubbed, because the default scrubber is not recursive. Fix: `include_local_variables=False`. Simulated fixes on a scratch copy: ai's allowlist plus `--tools ""` turns the first two pins green, but this pin stays red on `[setup_token]`, because a short env dict fits within Sentry's 10-item window and so ships the token. Adding `include_local_variables=False` turns all three green. |
| `…::test_floor2_cli_environment_is_exactly_the_reviewed_allowlist[…]` | SAFETY-057. The CLI child's env holds any name outside `CHILD_ENV_ALLOWED` (`PATH`, `HOME`, `LANG`, `LC_ALL`, `CLAUDE_CONFIG_DIR`, `CLAUDE_CODE_OAUTH_TOKEN`), e.g. a password-bearing `REDIS_URL` added to the adapter's allowlist, which the sentinel pin cannot see because nobody planted it. Also fails if a non-token run gets `CLAUDE_CODE_OAUTH_TOKEN`. Widening the child env is a floor-2 review: edit `CHILD_ENV_ALLOWED`. |
| `…::test_floor2_sentry_is_initialised_without_frame_locals` | SAFETY-057. `init_sentry` does not pass `include_local_variables=False` (layer 1 alone; the end-to-end pin goes red only when both layers are gone). |
| `…::test_floor2_scrub_event_drops_frame_locals[exception\|threads]` | SAFETY-057. `scrub_event` leaves `vars` on an exception or thread frame (layer 2 alone). |

Mutation-checked in SAFETY-053, each mutant on a scratch git repo, all caught: token on argv; token in `os.environ`; token dropped from `_credential_values`; auth retry despite a token; per-user env also given the token; api told the token path; `CLAUDE_CODE_OAUTH_TOKEN=` in `.env.example`; unpinned CLI; script writing the token 0644; script echoing the token; script personal-dir guard removed; `--rotate` ignored.

Mutation-checked in SAFETY-057 (scratch copy of services/app, `scratchpad/muts_057.py`), all caught: `--tools ""` dropped; `--tools default`; `DATABASE_URL` / `REDIS_URL` / `SENTRY_DSN` added to the adapter allowlist (the last two only by the exact-allowlist pin); child env `{**os.environ}`; pre-fix `env=None` + `{**os.environ, …}`; operator token handed to every mode; `include_local_variables=False` and the frame-vars scrub removed together, and each alone.

### Operator-only AI settings (SEC-01, SEC-03; backend `a5f3255`)

`claude_code_path` is the program the worker execs. Running a user's path runs their code next to the JWT secret, the DB URL and the instance keys, so it is held here.

| Test | Fails when |
|---|---|
| `test_floor2_operator_only_ai_settings.py::test_floor2_put_operator_only_ai_key_is_422_and_stores_nothing[…]` | `PUT /api/settings` naming `claude_code_path` or `claude_model` answers anything but 422, or stores anything. |
| `…::test_floor2_stored_legacy_path_and_model_never_reach_the_cli`, `…::test_floor2_get_user_ai_context_drops_stored_path_and_model`, `…::test_floor2_stored_legacy_model_never_reaches_the_anthropic_api` | A row stored before SEC-01 with a user path/model reaches the agent config, CLI argv[0], `--model`, or the Anthropic API adapter's model. |
| `…::test_floor2_factory_never_runs_a_user_supplied_executable_or_model` | **RED until ai fixes it (proposed M32-S4-AI-025).** `get_agent(user_settings={…"claude_code_path": X})` runs X. The factory is the single choke point, and it still forwards `cli_path`/`model`, which `ClaudeCodeAdapter` honours for `cli_path`. Only `_agent_config_from_overrides` builds the dict today and it drops the keys, so this is not reachable from a request now; one more builder would make it so. Fix: stop forwarding both keys and drop the adapter's `cli_path` override. Shown green on that fix in a scratch copy. |
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
| `…::test_floor2_host_login_copy_token_is_redacted_from_cli_failures[…]` | **RED until ai fixes it (proposed M32-S4-AI-025), `host_credentials_file` case.** The uid-mode copy built from `CLAUDE_HOST_CREDENTIALS_FILE` hands the child a token that is not in the adapter's redaction set (`_credential_values` covers `_host_credentials` only after a GL#8 retry, and the inode-pinned `~/.claude` file, which holds the pre-refresh token). A CLI failure quoting it puts the operator's token into the `AgentError`, so into `pipeline_runs.error_message` and the logs. Fix: record the copied login for redaction (`self._host_credentials = host_creds`) or re-read the file in `_credential_values`. Both shown green in a scratch copy. |

Mutation-checked in SAFETY-026, all caught: cwd not passed; cwd not removed; `model or …` restored; `--system-prompt` dropped; a flag after `--tools ""`; host copy read back (`not host`/`credentials` guards removed); copy dir not removed; uid not passed to spawn.

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
| `…::test_floor3_embed_texts_sites_equal_adr_0005_allowlist` | The pairs that reference `.embed_texts`, or the string `"embed_texts"` (a `getattr`), outside `agents/` and `pipeline/` are not exactly `EMBED_TEXTS_CALL_SITES`. |
| `…::test_floor3_startup_embedding_sites_never_embed` | `main.py:warn_if_embedding_provider_unavailable`, the startup probe, calls `embed_texts`. |
| `…::test_floor3_injected_provider_sites_have_only_worker_callers` | `index_service.index_artifact_chunks`, which embeds with a provider it is handed, is referenced from anywhere but `pipeline/index.py:_index`. |
| `…::test_floor3_pipeline_get_embedding_provider_only_in_celery_task_modules` | A `get_embedding_provider` reference under `app/pipeline/` is in a module that registers no Celery task. |
| `…::test_floor3_no_embedding_backend_reference_outside_agents` | `SentenceTransformerProvider`, `OpenAIEmbeddingProvider`, `OllamaEmbeddingProvider` or `reset_embedding_provider` is referenced outside `app/agents/**` as a name, attribute, import or exact string (docstrings and comments do not count), or a class there subclasses `EmbeddingProvider`. |
| `…::test_floor3_embedding_detectors_are_not_vacuous` | The collectors stop finding `pipeline/index.py:_index`, the `openai`, `sentence_transformers` and `ollama` imports in `agents/embeddings.py`, or `qa.ask_question`'s `embed_texts`. It also fails if a banned name is no longer defined in `agents/embeddings.py`, so a rename cannot leave the ban guarding nothing. |

The embedding checks were each shown red on an injected violation in a scratch copy
(M31-S2-SAFETY-021): a new request-side factory call, an aliased factory, a removed
listed site, a new `embed_texts`, a `getattr` string, the startup probe embedding, a
request-side caller of `index_artifact_chunks`, a factory call in a non-task pipeline
module, a `sentence_transformers` import, a backend class, `reset_embedding_provider`,
an `EmbeddingProvider` subclass, and the worker site removed.

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
| `…::test_r023_usage_day_is_utc_whatever_the_zone[...]` | With the clock frozen where `Pacific/Kiritimati` and `Etc/GMT+12` are on different dates, `get_usage_today`, `get_global_usage_today` or `record_usage` compares or writes a `record_date` other than the UTC date. Mutation-checked: `get_usage_today` on the Kiritimati day fails here and in the structural test. |
| `…::test_r023_zone_change_touches_no_usage_record` | Setting the zone touches `usage_records` or adds a row. |
| `…::test_r023_valid_timezone_refuses_hostile_keys_without_raising[...]` | `valid_timezone` raises or accepts a path-like, host-specific, NUL, surrogate, oversized, non-ASCII or non-string key. **RED until backend fixes it (SAFETY-037):** `localtime` is accepted on Debian hosts because `available_timezones()` walks the host's TZPATH and `/usr/share/zoneinfo/localtime -> /etc/localtime`. |
| `…::test_r023_accepted_zone_keys_come_from_the_declared_tzdata_only` | `valid_timezone` accepts a key that is not in the `tzdata` package's `zones` list, so the key set depends on the host or base image. **RED until the same fix.** |
| `…::test_r023_every_valid_key_fits_the_column` | A shipped key is longer than `user_settings.timezone`'s `String(64)`. |
| `…::test_r023_bad_stored_zone_degrades_to_utc[...]` | `user_now`, `user_today` or `local_day_end_utc` raises on, or does not answer in UTC for, a bad stored value. **RED on `localtime`**, which resolves to the host's zone. |
| `…::test_r023_listed_but_unloadable_zone_degrades_to_utc[...]` | A key that passes validation but fails to load (`ZoneInfoNotFoundError`, `ValueError` on a corrupt TZif, `OSError`) raises out of `user_now`/`user_today` instead of falling back to UTC. **RED until `clock._zone` guards `ZoneInfo(...)`**: ADR 0006 Decision 4 says a bad zone never raises in a request or a beat task. |
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

## Coverage

The floor tier is mostly static: it reads all of `app/**` but executes very little
of it, so a percentage of `app` is the wrong measure. Measure the tier's own guard
code, so that no detector branch goes dead:

```
pytest tests/safety --cov=tests/safety --cov-fail-under=95
```

The handoff for M31-S1-SAFETY-003 has the numbers and the proposal for a second
coverage measure: the floor-enforcing modules under unit and floor tiers together.

# Floor tier — floor to test map

The floor tier is `services/app/tests/safety/`, owned by `safety`. Every test runs
without Postgres, Redis or Docker: AST checks over `app/**`, FastAPI's test client
with dependency overrides, and mock sessions that record the SQL a handler builds.

Floors are quoted from `docs/strategy.md` §6. A floor is **green** only when every
test listed for it passes. An `xfail(strict=True)` test is a floor question that
is **waiting on the user's ruling**. It is not a pass. Each one says what the
ruling is about, and it turns red (XPASS) once the ruling lands, so the marker
has to come off at the same time.

Run:

```
cd services/app && .venv/bin/python -m pytest tests/safety -v
```

## 1. Tenant isolation

> an authenticated endpoint never returns or mutates another user's rows; every
> user-owned query filters on user_id

| Test | Fails when |
|---|---|
| `test_floor1_tenant_isolation.py::test_floor1_route_sweep_every_owned_query_filters_on_caller` | Any authenticated, non-admin route (every method), called with a type-valid request that carries a foreign value in every path parameter and every JSON body field (`_payload.py` builds it from the route's own types), runs a statement on a user-owned table that does not compare `user_id` to the caller's id. It also fails if `session.get()` is called on an owned model. It also fails if the sweep reaches fewer than 60 routes that query an owned table (74 at the M31 gate), because below that the check proves nothing. **RED until R-015 is fixed** (`backend`): `qa/ask`, `study/review`, `study/quiz-attempt`, `study/timed-plan`, `gamification/achievements/mark-notified`. |
| `…::test_floor1_route_sweep_owned_parent_never_unlocks_foreign_rows` | Same sweep, but every lookup that is scoped to the caller finds a row the caller owns, so handlers get past their ownership check. Fails when a later statement on an owned table is keyed on request input alone: it binds a planted value that no caller-scoped primary-key lookup has vetted, binds no id of the caller's own row, and has no `user_id` filter. A course *code* is never vetted, because it is unique per user, not globally. **RED until R-015 is fixed**: `GET /courses/{code}/weeks/{n}` (summary by code + week), plus the five routes above. |
| `…::test_floor1_route_sweep_reaches_every_handler` | A swept route is still rejected by FastAPI's request validation (a 422 with a field-error list), so its handler never runs and the sweep cannot see it. Only the multipart upload routes in `SWEEP_UNREACHED_BY_DESIGN` may be. It also fails if a listed route starts reaching its handler. |
| `…::test_floor1_payload_builder_plants_type_valid_foreign_values` | The request builder (`_payload.py`) stops producing a body that validates for a declared type (bounds, enums, literals, dates, UUIDs, nested models, a model-level "one of" rule), or stops planting a recognisable foreign value. The sweep is only as wide as this builder. |
| `…::test_floor1_every_table_is_classified` | A table is neither user-owned (it has `user_id`, a FK to an owned table, or is polymorphic) nor listed in `UNOWNED_TABLES`. |
| `…::test_floor1_no_unscoped_session_get_on_owned_model` | An `api/` or `services/` function calls `session.get(OwnedModel, <its own parameter>)` and the call is not classified. |
| `…::test_floor1_no_unscoped_query_function_outside_classification` | A `services/` or `pipeline/` function builds a query on a user-owned model, takes no caller parameter (`user_id`, `user`, …) that it uses, and puts no `<Model>.user_id` predicate or `filter_by(user_id=)` in it, and the function is not in `UNSCOPED_FUNCTION_ALLOWED` with a reason (worker-only, webhook, token lookup, FK traversal from a scoped parent). It also fails on a stale entry. This reaches code no route sweep can. **RED until R-015 is fixed**: `classify._get_known_courses` (`ai`), `achievement_service.mark_notified`, `summary_service.get_summary_for_week`, `timed_session_service.generate_timed_plan` (`backend`). |
| `…::test_floor1_unscoped_query_detector_is_not_vacuous` | The detector stops seeing two known worker-side unscoped reads. |
| `…::test_floor1_pipeline_only_fetch_is_pipeline_only` | The one allowlisted worker-only unscoped fetch gains a caller outside `app/pipeline/`. |
| `…::test_floor1_cannot_attach_document_to_another_users_assessment` | `attach_assessment_document` lets user B attach a document to user A's assessment. The fake session answers like a database: only a lookup filtered on the caller's `user_id` comes back empty, so an unscoped `select` fails too, and a control call as the owner must find the row. Fixed in M31-S1-BACKEND-008 (`a2cd687`). |
| `…::test_floor1_no_cross_user_route_awaits_a_ruling` | xfail(strict). The leaderboard is a cross-user read, pending a ruling. |

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
| `…::test_floor2_provider_error_never_echoes_a_stored_credential[<site>]` | A provider error that quotes every stored credential (the nested CLI token too) reaches the response, a structlog event or a stdlib log record at a request-time AI call site: `POST /api/settings/test-ai`, `POST /api/qa/ask`, `chat_service.send_message`, `chat_service.stream_message`, `POST /api/concepts/extract/{artifact_id}`. It also fails if no provider was called. The first four are green (R-008: `7eecbac` for test-ai, `718faa0` for qa and chat). The concepts site (ADR 0003 #5) runs the real adapter against a provider SDK that echoes the key it was sent (`_ProviderEcho`). **RED until** `ai` redacts at `AgentError` construction and `backend` stops `studyaio_error_handler` echoing `str(exc)` (R-012). |
| `…::test_floor2_worker_provider_error_never_stores_or_logs_a_credential[<site>-<backend>]` | Run eagerly as Celery tasks, `classify_artifact` and `process_course_document` hit a provider that echoes the key, for each of `anthropic_api`, `openai`, `zai` and `claude_code` (CLI stdout echoing the OAuth token). Fails if the credential reaches `pipeline_runs.error_message`, a structlog event, a stdlib log record (Celery's own `raised unexpected` line included) or the exception the task ends with. **RED until R-012 is fixed** (`ai`): classify stores it in `pipeline_runs.error_message`; courseops logs it as `courseops_document_failed`. |
| `…::test_floor2_global_handler_never_returns_or_logs_raw_agent_error` | An `AgentError` escaping a route reaches the client with any of its raw text, or the instance credential it quotes appears in the response or a log. **RED until** `backend` changes `main.studyaio_error_handler`, which returns and logs `str(exc)`. |
| `…::test_floor2_credentials_never_logged` | A stored credential appears in a structlog event or a stdlib log record during save, rejected save, or adapter construction for any backend. It also fails if one appears in a 422 body. |
| `…::test_floor2_no_high_confidence_secret_in_tracked_files` | A tracked file contains a private key block, or an AWS, Anthropic, OpenAI, GitHub, GitLab, Slack, Google, Stripe-live or Telegram credential in its fixed format. |
| `…::test_floor2_tracked_file_scan_fails_loudly_without_git[…]` | Git is missing, the tree is not a checkout, or `git ls-files` lists nothing, and the two committed-file checks do not fail. Until M31-S2 they silently scanned only `services/app`, which passed an AKIA sentinel committed under `docs/` in CI (pipeline 525, job 4301). |
| `…::test_floor2_no_env_file_tracked` | A `.env*` file other than a template is tracked. |
| `…::test_floor2_detect_secrets_baseline_is_wired_and_clean` | The pre-commit hook loses detect-secrets with `--baseline .secrets.baseline`, or loses `detect-private-key`. It also fails if a baseline entry is audited `is_secret: true`. |
| `…::test_floor2_sentinels_are_not_secret_shaped` | This tier's own sentinels would trip the scanner. |

## 3. AI only via the adapter (amended by ADR 0003)

> every AI call goes through AgentAdapter, obtained via `get_agent`; `get_agent` is
> called only in `app/pipeline/**` (the Celery worker) and at the request-time call
> sites enumerated in ADR 0003, and a new request-time call site requires amending
> that ADR

These are the checks from ADR 0003's Consequences section, in its order.

| Test | Fails when |
|---|---|
| `test_floor3_ai_via_adapter.py::test_floor3_request_time_get_agent_sites_equal_adr_0003_allowlist` | The set of `(module, enclosing function)` pairs that call `get_agent` outside `agents/` and `pipeline/` is not exactly `REQUEST_TIME_GET_AGENT_CALL_SITES`. Either direction fails: a site missing from the list, or a listed site that is gone. |
| `…::test_floor3_no_provider_sdk_import_outside_agents` | `anthropic`, `openai` or `ollama` is imported outside `app/agents/**`. That includes imports inside a function and `importlib` imports. |
| `…::test_floor3_no_adapter_class_reference_outside_agents` | An adapter class name is used outside `app/agents/**` as a name, an attribute, an import, or an exact string. Docstrings and comments do not count. |
| `…::test_floor3_no_claude_cli_spawn_outside_agents` | A subprocess or exec call outside `app/agents/**` has `claude` or `claude_code_path` as its program. |
| `…::test_floor3_pipeline_get_agent_only_in_celery_task_modules` | A `get_agent` call under `app/pipeline/` is in a module that registers no Celery task. |
| `…::test_floor3_detectors_are_not_vacuous` | The collectors stop finding the known pipeline call sites and SDK imports. |

**Embeddings (R-004) are not covered.** That gap is deliberate until the user rules
on R-004. Whichever way the ruling goes, it would add the following:

- **If embeddings are AI calls:** add `get_embedding_provider` to the floor-3 tests,
  checked the same way as `get_agent`. Its request-time call sites must equal an
  ADR-listed allowlist: `api/qa.py:ask_question`, `chat_service.send_message` and
  `stream_message`, and `concept_service`'s embedding helper. Then extend the SDK
  and class checks so that `OpenAIEmbeddingProvider` and `OllamaEmbeddingProvider`
  are built only through that factory.
- **If they are not AI calls:** pin that decision as well. Add a test that every
  `EmbeddingProvider` remote call still sits under `app/agents/**`, so that
  embeddings cannot become a way around floor 3 for generative calls.

## 4. User data is never lost

> nothing deletes uploads or generated content under data/ except explicit account
> deletion, and dedup/re-summarize never destroys prior versions

| Test | Fails when |
|---|---|
| `test_floor4_user_data_never_lost.py::test_floor4_every_blob_delete_is_classified` | A storage `delete`/`delete_prefix`, `unlink`, `os.remove` or `shutil.rmtree` under `app/` is not listed in `BLOB_SANCTIONED`, `BLOB_PENDING_RULING` or `BLOB_VIOLATIONS`. It also fails if a listed site no longer exists. |
| `…::test_floor4_every_content_row_delete_is_classified` | The same check for DB deletes of uploaded or generated-content models, and for every `session.delete`. |
| `…::test_floor4_account_purge_reachable_only_from_account_deletion` | `purge_user_storage` or `delete_user_account` gains a caller outside account deletion. |
| `…::test_floor4_lecture_upload_dedup_writes_and_deletes_nothing` | A duplicate lecture upload stores, deletes or dispatches anything. |
| `…::test_floor4_reference_checked_delete_has_only_classified_callers` | `_delete_blob_if_unreferenced` gains a caller not in `REFERENCE_CHECKED_DELETE_CALLERS`, or `discard_failed_upload_blob` is called from anywhere but the two courseops upload routes. The shared `store.delete` site is pending a ruling for the single-document delete and sanctioned for failed-upload cleanup, so its callers are pinned. |
| `…::test_floor4_duplicate_course_document_upload_keeps_original_blob` | Re-uploading the same course document deletes the blob the existing document's row points at. The fake session answers the reference count from real rows, so cleanup that skips the count fails. Fixed in M31-S1-BACKEND-008 (`a2cd687`). |
| `…::test_floor4_failed_assessment_attach_keeps_existing_blob` | A 404 on attach deletes a blob that an existing document uses (same fake). Fixed in `a2cd687`. |
| `…::test_floor4_failed_upload_never_deletes_another_users_blob` | User B's failed upload of user A's exact file deletes A's blob, or `discard_failed_upload_blob` deletes a key outside the caller's own `courseops/<user_id>/` prefix. |
| `…::test_floor4_resummarize_increments_version` | Re-summarizing a course and week does not increment `version`. |
| `…::test_floor4_resummarize_preserves_prior_version` | xfail(strict). Re-summarize overwrites version N-1, pending a ruling. |
| `…::test_floor4_asset_regeneration_keeps_study_history` | xfail(strict). Regeneration cascades away flashcard reviews and quiz attempts, pending a ruling. |
| `…::test_floor4_no_delete_site_awaits_a_ruling` | xfail(strict). Single-item user deletes and merge discards, pending a ruling. |

## Coverage

The floor tier is mostly static: it reads all of `app/**` but executes very little
of it, so a percentage of `app` is the wrong measure. Measure the tier's own guard
code, so that no detector branch goes dead:

```
pytest tests/safety --cov=tests/safety --cov-fail-under=95
```

The handoff for M31-S1-SAFETY-003 has the numbers and the proposal for a second
coverage measure: the floor-enforcing modules under unit and floor tiers together.

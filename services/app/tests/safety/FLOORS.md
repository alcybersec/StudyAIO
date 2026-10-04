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
| `test_floor1_tenant_isolation.py::test_floor1_route_sweep_every_owned_query_filters_on_caller` | Any authenticated, non-admin route (every method, with a foreign id in each path parameter) runs a statement on a user-owned table that does not compare `user_id` to the caller's id. It also fails if `session.get()` is called on an owned model. It also fails if the sweep reaches fewer than 60 routes that query an owned table (the floor is 74 today), because below that the check proves nothing. |
| `…::test_floor1_every_table_is_classified` | A table is neither user-owned (it has `user_id`, a FK to an owned table, or is polymorphic) nor listed in `UNOWNED_TABLES`. |
| `…::test_floor1_no_unscoped_session_get_on_owned_model` | An `api/` or `services/` function calls `session.get(OwnedModel, <its own parameter>)` and the call is not classified. |
| `…::test_floor1_pipeline_only_fetch_is_pipeline_only` | The one allowlisted worker-only unscoped fetch gains a caller outside `app/pipeline/`. |
| `…::test_floor1_cannot_attach_document_to_another_users_assessment` | **RED today.** `attach_assessment_document` resolves the assessment with no owner check. |
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
| `…::test_floor2_account_export_never_returns_a_stored_credential` | **RED today.** `GET /api/auth/account/export` returns `user_settings.settings_json` whole, credentials included. |
| `…::test_floor2_credentials_never_logged` | A stored credential appears in a structlog event or a stdlib log record during save, rejected save, or adapter construction for any backend. It also fails if one appears in a 422 body. |
| `…::test_floor2_no_high_confidence_secret_in_tracked_files` | A tracked file contains a private key block, or an AWS, Anthropic, OpenAI, GitHub, GitLab, Slack, Google, Stripe-live or Telegram credential in its fixed format. |
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
| `…::test_floor4_duplicate_course_document_upload_keeps_original_blob` | **RED today.** Re-uploading the same course document deletes the existing document's blob. |
| `…::test_floor4_failed_assessment_attach_keeps_existing_blob` | **RED today.** A 404 on attach deletes a blob that an existing document uses. |
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

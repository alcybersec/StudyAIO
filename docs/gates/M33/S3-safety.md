# M33 S3: floor review (M33-S3-SAFETY-059)

**Reviewer:** `safety` (veto role) · **Date:** 2026-10-15
**Tree:** `kit/retrofit` @ `aec844a`; reviewed range `569789f..aec844a` (17 commits, S3 wave 1 and the GL#51 compose
split). This review changes no `app/` code. It updates three floor-2 pins for the compose split and adds two floor
test files plus two helpers under `services/app/tests/safety/**`.

Floor text is the one in `docs/strategy.md` §6 as amended by ADR 0003, ADR 0004 and ADR 0005. The floor-to-test map
is `services/app/tests/safety/FLOORS.md`.

## Verdict: **APPROVE**

All four floors hold in the code at `aec844a` plus this review's test changes. The floor tier was red on 3 tests
after `aec844a`. The guards had not kept up with the compose split. No floor was breached. Section 4 lists the
non-blocking notes.

## 1. Part A: the floor-2 guards and the GL#51 compose split

### What was red

After `aec844a`, `make test`'s floor tier had 3 failures (`3 failed, 549 passed, 1 skipped`):

- `test_floor2_claude_login_mounts.py::test_floor2_compose_volume_parser_reads_the_dedicated_dir_mounts`
- `test_floor2_claude_login_mounts.py::test_floor2_only_the_worker_mounts_a_claude_login`
- `test_floor2_claude_oauth_token.py::test_floor2_only_the_worker_is_told_where_the_setup_token_is`

All three hard-coded the service name `worker`. The split added `worker-ondemand`, which has the same three
read-only dedicated-dir mounts and the same `CLAUDE_HOST_*` environment as `worker`, in `docker-compose.yml`,
`docker-compose.prod.yml` and `docker-compose.selfhosted.yml`.

### Ruling: `worker-ondemand` needs the login, `worker-maintenance` must not have it

`worker-ondemand` consumes `ai_ondemand`, and both tasks routed there call the agent:

- `app.pipeline.targeted_task.generate_targeted_items` → `_generate` → `get_agent` (pipeline, floor 3 allows it);
- `app.pipeline.concepts_task.extract_concepts` → `concept_service.extract_and_save_concepts` → `get_agent`. This is
  one of ADR 0003's enumerated call sites.

With the default `AGENT_BACKEND=claude_code`, that pool cannot work without the CLI login. Giving it the login is the
same exposure the single `worker` had before the split. It is the same image and the same read-only dedicated dir,
and the CLI child is sandboxed the same way (`test_floor2_cli_child_isolation.py`, `test_floor2_claude_oauth_token.py`).
So this is not a widening.

`worker-maintenance` consumes `maintenance`. Its 9 routed tasks are recovery (×2), notifications (×3), calendar
sync, backup and re-embed (×2). None of them reaches `get_agent`. Each step was checked statically:

- `recover_stuck_artifacts` → `resume_pipeline` *enqueues* the chain (`.s()`/`.apply_async()`), and those tasks run
  on the `pipeline` queue, not in-process.
- `recover_stuck_generations` only UPDATEs stuck rows.
- `reembed_user_chunks` → `pipeline.index._index` → `get_embedding_provider`. That is the instance-wide embedding
  gateway (ADR 0005), not `AgentAdapter`, and it reads no per-user credential.
- `reembed_all_chunks` only `.delay()`s per-user tasks.

### Guard change (an exact allowlist, not a relaxation)

- `CLAUDE_LOGIN_SERVICES = frozenset({"worker", "worker-ondemand"})` in `test_floor2_claude_login_mounts.py`, with
  the reason. The mount pin, the token-path pin (`…_only_the_ai_worker_pools_are_told_where_the_setup_token_is`),
  the parser self-check and the GL#8 pairing pin now apply to each allowlisted service, across every tracked compose
  file. `worker-maintenance`, `api`, `beat`, `ui` and any new service still fail.
- New `test_floor2_worker_pool_credentials.py` ties the allowlist to `app/worker.py`'s `_QUEUE_TASKS`. It uses a
  static call graph (`tests/safety/_callgraph.py`):
  - a maintenance task that reaches `get_agent` fails;
  - an allowlisted pool that consumes no AI queue fails, so the allowlist cannot just be widened;
  - a pool outside the allowlist that consumes an AI queue fails;
  - a not-blind check: the graph must see `get_agent` from all six known AI tasks and `get_embedding_provider` from
    re-embed, and must not mistake `.delay()` for a call.

### Revert checks (local, not committed)

| Mutation | Result |
|---|---|
| Add the login dir mount and `*claude-environment` to `worker-maintenance` in `docker-compose.yml` | mount pin and token-path pin red |
| Add `worker-maintenance` to `CLAUDE_LOGIN_SERVICES` | pool pin ("holds the Claude login but consumes no AI queue"), parser pin and pairing pin red |
| Route `extract_concepts` to `maintenance` in `app/worker.py` | `…_maintenance_tasks_never_reach_the_agent` and `…_claude_login_only_where_the_agent_is_called` red |

All files were restored. `git status` showed only `tests/safety/**` changes afterwards.

## 2. Part B: the S3 changes, by floor

### Floor 1: tenant isolation (holds)

- **Study-item CRUD** (`3c1ef9c`, `POST/PATCH/DELETE /api/assets/flashcards|quiz`):
  - `asset_service._owned_item` joins `Course` and filters `Course.user_id == user_id`. Foreign, missing and archived
    ids raise the same `ItemNotFoundError`, which maps to one identical 404, so the endpoint is not an existence
    oracle.
  - Create resolves the course with `get_course_by_code(..., user_id=)`. It takes the source lecture only from the
    caller's own artifacts in that course and week, and an explicit `source_artifact_id` is checked against both.
  - The copied `FlashcardReview` is read and written for the caller only.
  - The schemas carry no `user_id`.
  - Wiring is asserted in `tests/unit/api/test_asset_items_api.py`. Swapping every `user_id=user.id` in
    `app/api/assets.py` for another value turned all 10 wiring tests red.
  - New behavioural pins over MiniDB: `test_floor1_study_item_crud.py`.
- **Upload placement** (`?course_code=&week=`):
  - `course_service.get_or_create_course` matches `upper(code)` and `Course.user_id == user_id`, checks the course
    quota for the caller, and creates the course for the caller.
  - The artifact gets that `course_id`, the pipeline resumes at `extract` with the caller's `user_id`, and the dedup
    short-circuit runs before placement.
  - Swapping `user_id=user.id` in the two `get_or_create_course` calls turned `test_upload_placement.py`'s two wiring
    tests red.
  - New MiniDB pin: same code under two users, case-insensitive.
- **Chat delete (GL#52)**: `624d04a` is UI-only (a confirm dialog). `chat_service.delete_session` is unchanged. It is
  owner-scoped and is ADR 0004 item #4.
- **Transaction release (GL#50; `b53bff6`, `f102b73`, `7f27e44`)**: the new mid-request `session.commit()` calls in
  `qa.ask_question`, `chat_service.send_message`/`stream_message` and `concept_service.extract_and_save_concepts`
  commit only the caller's own pending rows: their message, the quota/metering row, their concepts. Every later query
  keeps its `user_id` predicate, as the route sweep and `test_floor1_retrieval_followup.py` (green) show. No other
  tenant's state can become visible through a committed partial state. Pipeline `release_connection` runs inside
  stages that act as `artifact.user_id`. It has no tenant dimension.

### Floor 2: no secrets (holds)

- See Part A for the login allowlist.
- The queue routing and the Celery messages carry ids only. No compose file or `.env.example` carries a token value,
  as `test_floor2_no_compose_or_env_template_carries_the_token_value` shows (green).
- `infra/deploy/deploy.sh` pings each Celery node by name (`inspect ping -d <node>@$HOSTNAME`). It reads and prints
  no secret.

### Floor 3: AI only via the adapter (holds)

- No new `get_agent` call site. The S3 changes move existing calls (commit before the call, embed via
  `asyncio.to_thread`) but do not add any. `test_floor3_ai_via_adapter.py` is green, and the ADR 0003/0005 call-site
  sets are unchanged.
- No AI task is routed to the pool without a login (Part A).

### Floor 4: user data is never lost (holds)

- **Edit** archives the original (`archived_at`), keeps its AI text, and inserts an `origin="user"` copy. Reviews stay
  on the original, the SRS schedule is copied to the new card, and attempts stay on the archived question.
- **Delete** is a soft delete (`archived_at`). Reviews and attempts are kept.
- **Judgement on the question asked:** a *hard* delete of a generated flashcard or quiz item would delete generated
  content. The floor permits that only on account deletion or for an item ADR 0004 enumerates, and flashcards and
  quiz items are not on that list. So a hard delete would have needed an ADR 0004 amendment with the user's agreement.
  The shipped code does not hard-delete, so no amendment is needed. `asset_service` has no SQL DELETE, and the
  floor-4 delete inventory (`test_floor4_every_content_row_delete_is_classified`) stays exact and green. The new pins
  fail on a `session.delete` in edit or archive (revert-checked: 4 red).
- **Pipeline regeneration** (`b53bff6`): `generate_assets` now saves both sets after both AI calls, so a failed quiz
  call no longer leaves a half-saved set. Prior items are still archived, not deleted. This is better than before.
- **Re-embed** (`index._index(refresh="apply")`): `release_connection(read_only=True)` rolls back, not commits,
  before the embed. The delete and insert of chunks happen in one fresh transaction after the vectors exist, so a
  failure leaves the old chunks in place.
- **`scripts/restore.sh`** now stops (and restarts) all three pools around the schema drop and restore. Before this
  fix, the two new pools would have kept writing during a restore.

## 3. Run evidence

Floor tier, the `make test-floor` command (worktree, main checkout's venv used read-only):

```
# before (aec844a, unchanged tier)
$ cd services/app && python -m pytest tests/safety -q
3 failed, 549 passed, 1 skipped, 33 warnings in 218.75s (0:03:38)

# after (this review)
$ cd services/app && python -m pytest tests/safety -v --cov=tests/safety --cov-report=term-missing --cov-fail-under=95
Required test coverage of 95% reached. Total coverage: 97.67%
=========== 567 passed, 1 skipped, 32 warnings in 389.32s (0:06:29) ============
```

The skip is the root-only setup-script check (`skipif(os.geteuid() != 0)`), which CI runs. Unit, golden and contracts
(`make test`'s first half, the same venv): `4025 passed`, coverage 91.52% (gate 75). `make test` itself was not run,
because its `bootstrap` step would build a venv in the worktree.

`_predicate.py` now models `upper()`/`lower()`, which `get_or_create_course` uses. The evaluator's self-test
(`test_floor1_predicate_evaluator_models_sql_semantics`) pins the new semantics and uses `length()` as its
not-modelled example.

## 4. Non-blocking notes (no veto)

1. **`worker-maintenance` runs as root.** It inherits `user: "0:0"` from `x-worker-common`, whose comment says root
   is "required for the Claude credential mounts", and this pool has none. Recommendation for `devops`: run it
   unprivileged, after checking that `/app/backups` and `backup.sh` work under that uid. This is least privilege, not
   a floor issue.
2. **"No AI credentials" means "no Claude CLI login".** Every service, `worker-maintenance` included, gets `.env`
   through `env_file`, so the instance `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` (if set) and `SETTINGS_ENCRYPTION_KEY`
   are present. Re-embed needs the OpenAI key when `EMBEDDING_BACKEND=openai`. That is not a floor-2 breach: nothing
   is committed, logged or returned. The `docker-compose.yml` comment and `docs/deployment.md` should say "no Claude
   login" so the claim stays accurate (`devops`).
3. **The call graph under-approximates.** It does not follow instance method calls or functions reached only through
   module-level containers. The not-blind pin covers the known AI paths. A new AI task on `maintenance` that is only
   reachable that way would be missed until its own floor-3 review.

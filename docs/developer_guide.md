# StudyAIO — Developer Guide

This guide covers everything needed to develop, test, and extend StudyAIO.

---

## 1. Prerequisites & Setup

### System Requirements

- **Docker** 24+ with Docker Compose v2
- **Node.js** 20+ (for local frontend development)
- **Python** 3.12+ (for running tests/scripts outside Docker)
- **Claude Code CLI** (for AI pipeline stages)

### Claude CLI Authentication

The processing pipeline uses Claude Code CLI for classification, summarization, and asset generation. The CLI binary and credentials are bind-mounted from the host into the worker container.

```bash
# Install Claude Code CLI
npm install -g @anthropic-ai/claude-code

# Login (opens browser for OAuth)
claude
```

This creates `~/.claude/.credentials.json`, which the worker container mounts.
The CLI binary itself is installed in the image, so only the credentials (and
optionally `~/.claude/settings.json`) come from the host. Do not bind-mount a
host `claude` binary over `/usr/local/bin/claude` — that path is a symlink into
the npm package, and Docker resolves it onto `bin/claude.exe`, which node then
refuses to load.

Per-user credentials configured in Settings → AI take precedence over the
mounted file; they are written to a temporary `CLAUDE_CONFIG_DIR` per call.

### Environment Configuration

```bash
cp .env.example .env
```

Key variables:
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` — database credentials
- `DB_PORT` — host port for Postgres (default: `5433`, avoids conflict with host Postgres)
- `REDIS_PORT` — host port for Redis (default: `6380`)
- `UI_PORT` — host port for the UI (default: `3001`)
- `CLAUDE_CONFIG_DIR` — path to Claude config directory on host (default: `~/.claude`)
- `AGENT_BACKEND` — which AI adapter to use: `claude_code` (default), `anthropic_api`, `openai`, or `ollama`. Each has its own key/model variables in `.env.example`. Credentials saved per user in Settings override these.
- `SELF_HOSTED` — `true` (default) skips auth and uses a single default admin user; `false` enforces login

`.env.example` lists every setting in `app/config.py`, commented out where the
default is fine.

### First Launch

```bash
docker compose up -d    # Start all services (builds images on first run)
make migrate            # Run Alembic database migrations
make seed               # (Optional) Populate with demo data
```

Verify:
- **UI**: http://localhost:3001
- **API**: http://localhost:8000/docs (Swagger)
- **Health**: http://localhost:8000/health

---

## 2. Development Workflow

### Forge: GitLab is canonical

**Everything lives on GitLab** — code, issues, merge requests and CI. As of
2026-09-27 GitHub is not used for any of it.

| | Where | How |
|---|---|---|
| Code | `origin` → `git@192.168.1.174:alcybersec/StudyAIO.git` | `git push origin <branch>` |
| Issues | GitLab issues | `glab issue list` / `create` / `view` / `close` |
| Reviews | GitLab merge requests | `glab mr create` / `view` / `merge` |
| CI | `.gitlab-ci.yml` | `glab ci list` / `get` / `trace` / `retry` |

`glab` is installed and authenticated against `gitlab.home.aleksanlab.me`
(`glab auth status` to confirm). Prefer it over raw `curl` — it already holds the
token and resolves the project from the remote.

The GitHub repository is kept for exactly two things and **must not be used for
anything else**: it is the GHCR namespace the build jobs publish images to
(`ghcr.io/${GHCR_OWNER}/studyaio-{api,ui}`, which prod compose pins and the
deploy host logs in to pull), and it receives a push mirror from GitLab. It holds
no open issues — the four that were there moved to GitLab as GL#2–GL#5 — and it
has no workflows, since `.github/` was deleted when CI moved.

Pushing to it from a working copy is therefore always a mistake, and
`git remote set-url --push github DISABLED-USE-GITLAB` makes that fail loudly
rather than silently diverging from the mirror. Fetch still works, so the
history stays readable. Undo with
`git remote set-url --push github https://github.com/alcybersec/StudyAIO.git` if
you ever genuinely need it.

> **Do not open issues, PRs or reviews on GitHub, and do not consult GitHub
> issues for current state.** Issue numbers below GL#6 in older documents
> (`docs/security-review-2026-09.md`, `PROGRESS.md`) are *GitHub* numbers from
> before the move; the mapping is #90→GL#2, #101→GL#3, #107→GL#4, #108→GL#5.

### Branch and merge

Branch off `main`, push to `origin`, open an MR, let the pipeline run, merge.
`main` is protected, and since 2026-09-28 a **green pipeline is enforced, not
merely conventional** (GL#2):

| Setting | Value |
|---|---|
| `allow_force_push` | `false` |
| `only_allow_merge_if_pipeline_succeeds` | `true` |
| `allow_merge_on_skipped_pipeline` | `false` |
| push access | **No one** |
| merge access | Maintainers |

The second and third go together. Requiring pipeline success while still allowing
a merge on a *skipped* pipeline reproduces the hole at the merge gate that the
deploy job's shell ref-guard exists to close: a skipped job reports the run
green, so "succeeded" and "never ran" would be indistinguishable.

**`git push origin main` is refused for everybody**, so a merge request is the
only way in. Push access and merge access are separate levels: "No one" governs
pushes, while merges are performed server-side under `merge_access_level`, so
MRs are unaffected.

That closes the last gap in GL#2. It matters here more than on most projects
because `main` auto-deploys on success — a direct push would otherwise reach
production with no pipeline in front of it.

Nothing automated is affected: no CI job or script runs `git push`, `git commit`
or `git tag`; `deploy-selfhosted` sends only a commit SHA over SSH and the host
checks it out; and the GitHub mirror is *outbound* (GitLab → GitHub), which
protected-branch push rules do not govern.

Work on a branch and open an MR — including for a one-line fix, and including
when you are the only person on the repository.

> **A commit message that merely *mentions* `[skip ci]` skips the pipeline.**
> GitLab scans the entire message for that token, not just a leading tag, so
> writing about it — "the commits carry no `[skip ci]`" — is enough to trigger
> it. The pipeline is then created with **zero jobs** and reported `skipped`,
> which is not obviously distinguishable from a CI misconfiguration.
>
> Since `allow_merge_on_skipped_pipeline` is `false`, that also makes the MR
> unmergeable. This bit exactly once, on the branch documenting the gate.
> Write it as "a skip-ci directive" in prose; the literal token is fine in a
> file, only commit messages are scanned.

Commit messages and MR descriptions must not mention the tooling used to write
them.

### Backend Development

The API and worker containers bind-mount source code from `services/app/app/` and `services/app/prompts/`. The API runs with `--reload`, so code changes take effect immediately:

```bash
# Edit backend code
vim services/app/app/api/courses.py

# API auto-reloads — check logs
make logs-api
```

The worker does NOT auto-reload. Restart it after code changes:

```bash
docker compose restart worker
```

### Frontend Development

The production UI Dockerfile builds static assets served by nginx. For development with hot module replacement (HMR), run the Vite dev server locally:

```bash
cd services/ui
npm install
npm run dev    # Starts at http://localhost:3000 with HMR
```

The Vite config proxies `/api` requests to `http://localhost:8000`, so the API container must be running. SSE events also route through the dev server proxy.

To test the production build locally:

```bash
docker compose build ui
docker compose up -d ui
# Visit http://localhost:3001
```

### Database Migrations

All schema changes go through Alembic:

```bash
# Create a new migration after editing models
make migration
# Enter description when prompted, e.g.: "Add priority column to review_items"

# Apply pending migrations
make migrate

# Check migration status
docker compose exec api alembic current
docker compose exec api alembic history
```

Always review the generated migration file before applying — auto-generate doesn't handle pgvector `Vector` imports automatically.

### Prompt Editing

AI prompts live in `services/app/prompts/` as Jinja2 `.txt` files. They're bind-mounted into the worker container, so changes are picked up on the next pipeline run without a restart.

Test prompt changes by re-processing a file:

```bash
# Upload a test file through the UI, or:
make ingest path=/path/to/test.pdf
```

---

## 3. Adding Features

### Adding an API Endpoint

1. Create or edit a router in `services/app/app/api/`:
   ```python
   # app/api/my_resource.py
   from fastapi import APIRouter, Depends
   from sqlalchemy.ext.asyncio import AsyncSession
   from app.api.deps import get_current_user_or_default
   from app.core.database import get_session
   from app.models.user import User

   router = APIRouter(prefix="/api/my-resource", tags=["My Resource"])

   @router.get("")
   async def list_items(
       user: User = Depends(get_current_user_or_default),
       session: AsyncSession = Depends(get_session),
   ):
       # Call service layer — keep routes thin, and pass the caller's identity
       # into every lookup that touches user-owned data.
       return await my_service.list_items(session, user_id=user.id)
   ```

   The identity dependency is not optional: `test_endpoint_authn_guard.py` walks
   every route and fails on one that answers an anonymous caller. Anything that
   resolves an id out of the path or query must additionally carry `user_id`
   into the lookup — see [Owner-Scoped Endpoints](#owner-scoped-endpoints-assert-the-wiring).

2. Register the router in `app/main.py`:
   ```python
   from app.api.my_resource import router as my_resource_router
   app.include_router(my_resource_router)
   ```

3. Add Pydantic schemas in `app/api/schemas.py`.

4. Write tests in `tests/unit/api/test_my_resource.py`. If the endpoint is
   owner-scoped, the test must assert the *wiring* and not only the status code
   — see [Owner-Scoped Endpoints](#owner-scoped-endpoints-assert-the-wiring).

### Adding a Pipeline Stage

1. Create a Celery task in `app/pipeline/my_stage.py`:
   ```python
   from app.worker import celery_app
   from app.core.database import run_async

   @celery_app.task(bind=True, max_retries=3)
   def my_stage_task(self, input_data: str | dict) -> str:
       artifact_id = input_data if isinstance(input_data, str) else input_data["artifact_id"]
       run_async(_process(artifact_id))
       return artifact_id

   async def _process(artifact_id: str):
       # Business logic here — use async session
       ...
   ```

2. Add the task to the chain in `app/pipeline/orchestrator.py`.

3. Tasks must be **idempotent** — safe to retry on failure.

### Adding a Frontend Page

1. Create a page component in `services/ui/src/pages/MyPage.tsx`.
2. Add a route in `services/ui/src/router.tsx`.
3. Add a nav item in `services/ui/src/components/layout/Sidebar.tsx`.
4. Use React Query hooks from `services/ui/src/hooks/useApi.ts` for data fetching.

---

## 4. Testing

### Test Structure

```
services/app/tests/
├── conftest.py           # Shared fixtures (mock_session, simple_pdf/docx/pptx, etc.)
├── unit/                 # Fast tests, everything mocked
│   ├── api/              # API endpoint tests (httpx AsyncClient)
│   ├── extractors/       # PDF/DOCX/PPTX extractor tests
│   ├── pipeline/         # Celery task tests
│   └── services/         # Business logic tests
├── integration/          # Real Postgres + Redis (see below)
│   └── conftest.py       # Env-var contract + SAVEPOINT fixtures
└── golden/               # Structural validation tests
    ├── conftest.py       # Sample manifests, summaries, asset fixtures
    ├── test_extraction_structure.py
    ├── test_summary_structure.py
    └── test_asset_structure.py
```

### Running Tests

```bash
make test               # All unit tests
make test-unit          # Unit tests only
make test-integration   # Integration tests (starts Postgres + Redis for you)
make test-golden        # Golden structural tests
make coverage           # Unit tests with coverage report
```

### Integration Tests

`tests/integration/` runs against a real Postgres (with pgvector) and a real
Redis. Both are addressed by three environment variables that **must be exported
before pytest starts**:

```
DATABASE_URL        postgresql+asyncpg://<user>:<pass>@<host>:<port>/<db>
DATABASE_URL_SYNC   postgresql://<user>:<pass>@<host>:<port>/<db>
REDIS_URL           redis://<host>:<port>/0
```

`make test-integration` (`scripts/test-integration.sh`) starts throwaway
containers, exports all three, runs the suite and removes the containers again.
If `DATABASE_URL` is already set it uses your services instead and starts
nothing — which is exactly what CI does with its service containers, so local
runs and CI take the same code path.

Setting those variables from inside a fixture is too late. `app.config.settings`
reads the environment once at import; `app.core.database.engine` and
`app.core.redis.redis_client` are constructed at import from that singleton and
never re-read it. An `importlib.reload()` does not help, because every module
that already did `from app.core.database import async_session_factory` still
holds the old object. The conftest therefore checks the app's *resolved* engine
URL against `DATABASE_URL` and fails with an explanation on a mismatch, instead
of hanging against the compose hostname `db:5432` (issue #56).

Or inside the container:

```bash
docker compose exec api pytest tests/unit -x -v
docker compose exec api pytest tests/golden -x -v
```

### File Storage During Tests

`DATA_DIR` needs no setup: `services/app/conftest.py` points it at a fresh
throwaway directory before `app.config` is first imported, and deletes it when
the process exits. `scripts/test-integration.sh` exports the same thing so
Alembic and any subprocess resolve the same root.

This is not cosmetic. `settings.data_dir` defaults to `/app/data` — right inside
the container, where it is the bind-mounted `./data`, and wrong on the host,
where it may be a populated upload directory. `LocalStorageBackend` creates that
directory on construction and the account-deletion path deletes from it, so a
test that reached `get_storage()` without a fixture could write into, or delete
from, real data. Nothing was ever lost only because those tests use random UUIDs
(issue #100). Note that this applies to the in-container commands above too: the
suite is redirected away from `/app/data` there as well, with a warning on
stderr saying so.

An inherited `DATA_DIR` is honoured only when it is already a temp path;
anything else is replaced. If `settings.data_dir` still ends up outside the
system temp directory, the run aborts with an explanation rather than touching
files — there is deliberately no opt-out. Point `DATA_DIR` at a temp directory of
your own if you need a specific location.

Individual tests still take a `tmp_path`-rooted storage fixture — `storage` in
`tests/integration/conftest.py`, or the per-test root the same file installs
automatically. The global redirect is the floor that stops the suite reaching
real data; the per-test root is what stops one test reading another's files.

### End-to-End Tests

The Playwright suite lives in `services/ui/e2e/` and drives a running stack — it
does **not** start one for you.

```bash
make up                 # API on :8000, UI on :3001
make test-e2e           # or: cd services/ui && npm run test:e2e
cd services/ui && npm run test:e2e:ui   # interactive runner
```

Override the targets with `E2E_BASE_URL` and `E2E_API_URL` if your ports differ.
Several specs call `test.skip()` when the data or the auth mode they need isn't
present (self-hosted vs SaaS), so skipped tests are expected, not failures.

### Continuous Integration

`.gitlab-ci.yml` runs on every branch push — GitLab attaches the branch pipeline
to any merge request for that branch — in five stages: `lint`, `test`, `e2e`,
`build`, `deploy`. Python lint (`ruff check` **and** `ruff format --check`),
backend unit + golden tests with a 75% coverage floor, integration tests against
real Postgres + Redis, frontend typecheck/lint/unit/build with the color-token
and bundle-size guards, and the Playwright suite. Jobs are `interruptible` by
default, so a newer push cancels the run it supersedes.

Every job runs on the homelab runners and must carry tags — they are registered
`run_untagged:false`, so a tagless job would sit pending forever. The default is
`[homelab, docker]`; the two image-build jobs override it to `[shell]` because
they need a real host Docker socket, which the docker runner does not have.

`build-api`/`build-ui` and `deploy-selfhosted` run only on `main` or a `v*` tag.
They build and push the GHCR images and deploy VM 210. Images deliberately still
go to **GHCR**, not the GitLab registry: `docker-compose.prod.yml` pins
`ghcr.io/${GHCR_OWNER}/studyaio-{api,ui}` and the deploy host logs in to GHCR to
pull, so the migration changed only *who runs the build*. Deploy takes
`resource_group: studyaio-prod` so two deploys never interleave, and it re-checks
the ref in the shell rather than relying on `rules:` alone — a `rules:` mismatch
*skips* the job, and a skipped job reports the pipeline green, which would read as
a successful deploy that never happened.

The E2E job reproduces the stack without Docker. It runs *inside* a container, so
Postgres and Redis are reached by service alias while the API and the previewed UI
are on `localhost` because the job starts them itself. Note that GitLab derives a
service alias from the image name: `redis:7-alpine` is already `redis`, but
`pgvector/pgvector:pg16` derives to `pgvector`, so it carries an explicit
`postgres` alias. There is also no `--health-cmd` equivalent — services start in
parallel with the job, so readiness is the job's own `before_script`. No Celery
worker runs there; the suite asserts that uploads are accepted and queued, never
that the pipeline completes.

> CI moved from GitHub Actions to GitLab CI on 2026-09-27. `.github/workflows/`
> is gone; the GitHub repository is kept only as the GHCR image namespace. Issues
> live on GitLab.

### Summary Quality Evals

`tests/golden/` checks that a summary has the right **shape**. Nothing checked
whether it was any **good** — so a change to `prompts/summarize.txt` could be an
improvement or a regression and the suite said the same thing either way.

```bash
# Deterministic scores only: no model, no credentials, no cost
docker compose exec api python -m app.cli evals --no-judge

# With model-graded faithfulness (two AI calls per case)
docker compose exec api python -m app.cli evals

docker compose exec api python -m app.cli evals --case normalisation

# Three runs of each case: generation is non-deterministic, so one run is a
# sample. This separates a fabrication that happens every time from one that
# happened once. Multiplies the cost by N.
docker compose exec api python -m app.cli evals -n 3 --out /app/data/evals-$(date +%F).json
```

**Read `-n` output for stability first.** A case marked `UNSTABLE` did not agree
with itself across runs, which means its numbers are not repeatable and
comparing them against a previous run tells you nothing — a different problem
from failing. `FABRICATED every run` is a property of the prompt and worth
fixing; `fabricated sometimes (1/3 runs)` is the model's temperature and may not
be.

**Not part of CI, on purpose.** It costs money and is not deterministic, and a
non-deterministic gate is worse than no gate — it would fail randomly and get
ignored, taking the rest of the pipeline's credibility with it. Run it by hand
when a prompt changes and read it against the previous run; `--out` exists so
two runs can be diffed.

Four scores, of which only the last needs a model:

| Score | How | What a drop means |
|---|---|---|
| Coverage | Terms from `must_mention` present | The summary dropped something the lecture taught |
| **Fabrication** | Terms from `must_not_mention` present | The summary told a student their lecture covered something it never mentioned |
| Structure | Sections derived from the prompt itself | The output stopped following its own format |
| Faithfulness | Model graded, 1–5 | It asserts something the source does not support |

Fabrication is the one to watch. Each case's `must_not_mention` lists the
*adjacent* topics a model is most likely to volunteer from general knowledge —
BCNF after third normal form, CUBIC after Reno. Those are not wrong about the
world; they are wrong about the lecture, and for a study tool that is the
failure that matters.

Faithfulness deliberately does **not** decide pass or fail: it is one model's
opinion, and gating on it would make the result depend on which backend happened
to judge.

**Adding a case.** Drop a JSON file in `services/app/evals/cases/`. It needs
`id`, `pages`, `must_mention`, `must_not_mention` and `notes` saying why those
terms were chosen — the reasoning is the part a later reader cannot reconstruct.
`tests/unit/test_eval_harness.py` validates every case: each `must_mention` must
actually appear in its own source, and no `must_not_mention` may, or the case
would produce a confident wrong number. Keep the source synthetic, per
`.claude/rules/tests.md`.

### Key Testing Patterns

**Mocking async services in pipeline tests:**
```python
from unittest.mock import AsyncMock, patch

@patch("app.pipeline.classify.classify_service.classify")
async def test_classify_task(mock_classify):
    mock_classify.return_value = AsyncMock(...)
```

**API tests with dependency injection:**
```python
async def test_list_courses(async_client, mock_session):
    mock_session.execute.return_value = MockResult(...)
    response = await async_client.get("/api/courses")
    assert response.status_code == 200
```

**Integration tests use SAVEPOINT isolation** — each test runs in a transaction that rolls back, so tests don't affect each other.

**Golden tests validate structure, not content** — they verify that extractors produce correct manifest schemas, summaries contain all 8 sections, and assets have required fields.

### Owner-Scoped Endpoints: Assert the Wiring

Any endpoint that resolves a request-supplied id must thread the caller's
identity into the lookup, and **its test must assert that it did**:

```python
async def test_get_exam_progress_404_for_other_user(async_client, default_test_user):
    async def scoped(session, exam_id, user_id=None):
        return {"id": exam_id} if user_id == OWNER_A else None

    mock = AsyncMock(side_effect=scoped)
    with patch("app.api.exams.exam_service.get_exam_progress", new=mock):
        response = await async_client.get("/api/exams/exam-owned-by-a")

    assert response.status_code == 404
    assert mock.await_args.kwargs.get("user_id") == default_test_user.id   # ← load-bearing
```

The status assertion on its own passes with the fix reverted: the mock returns
`None` whichever id it is handed, so a completely unscoped endpoint still 404s.
Every revert check run during the #47/#53/#58 fixes showed the same pair —
`assert response.status_code == 404` green, the wiring line red. Where the
identity is passed positionally, assert on `mock.await_args.args[n]` instead.
`tests/unit/api/test_scoped_api.py` and `tests/unit/api/test_idor_scoping.py`
are the worked examples.

Two traps this has actually sprung:

- **A mention of `user.id` is not scoping.** Before #53, `resolve_review_item`
  passed `user_id=user.id` to `resume_pipeline` for logging while looking the
  review item itself up unscoped. Assert on the mock for *the lookup*, not on
  the handler's source and not on some other call it happens to make.
- **A status code with several causes proves nothing.**
  `test_dismiss_already_resolved_returns_400` was passing on a 400 raised by an
  ownership miss, not by the already-resolved branch it exists to cover
  (#58/PR #62). Where a status has more than one cause, assert the cause — the
  `detail` string, or a fixture arranged so only the branch under test can fire.

Three structural guards cover the endpoints nobody has written yet, and will
fail a PR that adds an unprotected route:

| Guard | Question it asks |
|---|---|
| `tests/unit/api/test_endpoint_authn_guard.py` | does this route require a caller at all? |
| `tests/unit/api/test_endpoint_scoping_guard.py` | does an id-addressed lookup carry the caller's identity? |
| `tests/unit/api/test_subscription_scoping_guard.py` | is the pub/sub channel it subscribes to the caller's own? |

The guards prove an identity is passed. The per-endpoint wiring assertion is
what proves it is the *right* one, so both are needed.

**Verify a new wiring assertion by reverting the fix.** Strip the
`user_id=user.id` from the endpoint, run the test, and confirm it fails on the
wiring line and not on the status line. An assertion nobody has watched fail is
worth nothing.

---

## 5. Architecture Quick Reference

### Module Map

| Module | Purpose |
|--------|---------|
| `app/api/` | Thin HTTP routes — validate → call service → return response |
| `app/services/` | Stateless business logic — receives sessions as params |
| `app/pipeline/` | Celery tasks — thin wrappers calling services/agents |
| `app/agents/` | AI adapter interface + implementations |
| `app/extractors/` | File parsers (PDF/DOCX/PPTX → ExtractionResult) |
| `app/models/` | SQLAlchemy ORM models (one per file) |
| `app/core/` | `database.py` (async engine + `run_async`), `cache.py`/`redis.py`, `storage.py` (local/S3), `auth.py` + `security.py` + `oauth.py`, `quota.py`, `rate_limit.py`, `logging.py`, `exceptions.py` |

### Request Flow

```
Browser → nginx (port 3001)
  → /api/* → proxy to FastAPI (port 8000)
       → Router → Service → Database
  → /* → serve static React app (SPA fallback)
```

### Pipeline Flow

```
Upload → ingest_file → classify_artifact → extract_artifact
  → summarize_artifact → index_artifact → generate_assets
```

Each stage is a Celery task chained via
`orchestrator.run_pipeline(file_path, user_id, artifact_id)`.
Stages pass a dict along the chain — `{"file_path", "user_id", "artifact_id"}` into
`ingest_file`, then `{"artifact_id", "user_id"}` onward — so ownership is threaded
through for multi-tenant isolation.

`POST /api/uploads` hashes the bytes, checks for a duplicate and creates the
artifact row **inside the request**, then passes that `artifact_id` in. That is
what lets the response return a real id the client can filter the SSE stream by
and retry against; ingest adopts the row instead of creating one. Called without
an `artifact_id`, `ingest_file` still hashes, dedups and creates as before. `resolve_pipeline_input()` accepts either that dict or a
bare `artifact_id` string, and each task opens its own database session.

`orchestrator.resume_pipeline(artifact_id, from_stage=...)` restarts the chain from
any stage; that is what `POST /api/uploads/{artifact_id}/retry` calls.

### Key Patterns

- **Agent Adapter**: All AI calls go through `AgentAdapter` ABC. Never call Claude directly outside `claude_code.py`.
- **`run_async()`**: Shared coroutine runner in `database.py` that disposes the sync engine before each call to avoid event loop conflicts in Celery workers.
- **Chain Compatibility**: Pipeline tasks accept `str | dict` input and return the artifact ID string for the next task in the chain.
- **Embedding Provider**: Separate from AgentAdapter — uses sentence-transformers locally (deterministic, no API calls).
- **SSE Events**: Published via Redis pub/sub from pipeline tasks, consumed by the API's SSE endpoint.

---

## 6. Troubleshooting

### Event Loop Errors in Worker

**Symptom:** `RuntimeError: Event loop is closed` or `attached to a different loop`

**Cause:** Celery workers reuse processes. SQLAlchemy's async engine pool binds to the first event loop, which is closed when the task completes.

**Fix:** The shared `run_async()` function calls `engine.sync_engine.dispose()` before each coroutine to reset the connection pool. If you see this error, ensure your pipeline task uses `run_async()` instead of `asyncio.run()`.

### Claude CLI Authentication

**Symptom:** `claude: command not found` or authentication errors in worker logs.

**Fix:**
1. Verify the CLI works *inside* the container: `docker compose exec worker claude --version`
   (if this fails with `ERR_UNKNOWN_FILE_EXTENSION ".exe"`, a host binary is
   being bind-mounted over `/usr/local/bin/claude` — remove that volume)
2. Verify credentials exist: `ls ~/.claude/.credentials.json`
3. Check `CLAUDE_CONFIG_DIR` in `.env`
4. Re-authenticate: run `claude` on host, complete OAuth flow — or paste
   credentials per-user under Settings → AI

### Port Conflicts

The default ports are chosen to avoid common conflicts:
- PostgreSQL: `5433` (not 5432) — set `DB_PORT` in `.env`
- Redis: `6380` (not 6379) — set `REDIS_PORT` in `.env`
- UI: `3001` (not 3000) — set `UI_PORT` in `.env`

If a port is still in use:

```bash
# Find what's using the port
ss -tlnp | grep 5433

# Change in .env
DB_PORT=5434
```

### Container Logs

```bash
make logs           # All services
make logs-api       # API only
make logs-worker    # Worker only
docker compose logs -f db     # Database
docker compose logs -f redis  # Redis
```

### Database Issues

```bash
# Connect to psql shell
make db

# Check table existence
\dt

# Reset database (DESTRUCTIVE)
make reset-db
make migrate
```

### Frontend Build Failures

If `docker compose build ui` fails:

```bash
cd services/ui
npm ci           # Clean install
npm run build    # Test build locally
npm run lint     # Check for lint errors
npx tsc --noEmit # Check TypeScript
```

### Production Mode

```bash
make build-prod     # Build production images
make up-prod        # Start with production settings
make down-prod      # Stop production services
```

Production differences:
- nginx serves static UI (no Vite dev server)
- API runs multi-worker uvicorn without `--reload`
- Worker runs with higher concurrency (`--concurrency=4`)
- DB and Redis ports not exposed to host
- All services set to `restart: unless-stopped`

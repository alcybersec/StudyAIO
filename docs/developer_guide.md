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
   from app.core.database import get_session

   router = APIRouter(prefix="/api/my-resource", tags=["My Resource"])

   @router.get("")
   async def list_items(session: AsyncSession = Depends(get_session)):
       # Call service layer — keep routes thin
       return await my_service.list_items(session)
   ```

2. Register the router in `app/main.py`:
   ```python
   from app.api.my_resource import router as my_resource_router
   app.include_router(my_resource_router)
   ```

3. Add Pydantic schemas in `app/api/schemas.py`.

4. Write tests in `tests/unit/api/test_my_resource.py`.

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
├── integration/          # Real DB + Redis (testcontainers)
│   └── conftest.py       # Testcontainers + SAVEPOINT fixtures
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
make test-integration   # Integration tests (needs Docker services)
make test-golden        # Golden structural tests
make coverage           # Unit tests with coverage report
```

Or inside the container:

```bash
docker compose exec api pytest tests/unit -x -v
docker compose exec api pytest tests/golden -x -v
```

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

`.github/workflows/ci.yml` runs on every pull request and on pushes to
`main`/`master`/`develop`: Python lint, backend unit + golden tests with a 75%
coverage floor, integration tests against real Postgres + Redis, frontend
typecheck/lint/unit/build with the color-token and bundle-size guards, and the
Playwright suite. A newer push to a PR cancels the run it supersedes.

CI runs on GitHub-hosted runners. The self-hosted homelab runner is reserved for
`.github/workflows/deploy.yml`, which builds and pushes the GHCR images and
deploys — so a long test run never sits in front of a deploy.

The E2E job reproduces the stack without Docker: Postgres and Redis as service
containers, the API under uvicorn, and the production bundle from the frontend
job served by `vite preview` (its `/api` proxy is configured in
`vite.config.ts`). No Celery worker runs there — the suite asserts that uploads
are accepted and queued, never that the pipeline completes.

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

Each stage is a Celery task chained via `orchestrator.run_pipeline(file_path, user_id)`.
Stages pass a dict along the chain — `{"file_path", "user_id"}` into `ingest_file`,
then `{"artifact_id", "user_id"}` onward — so ownership is threaded through for
multi-tenant isolation. `resolve_pipeline_input()` accepts either that dict or a
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

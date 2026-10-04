.PHONY: bootstrap up down logs test test-unit test-floor test-integration test-golden test-e2e migrate shell db status build clean ingest import-v0 seed seed-demo lint-python lint-python-fix coverage up-prod down-prod build-prod up-selfhosted down-selfhosted backup restore preflight ensure-admin

# === Docker ===
up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

# === Production ===
up-prod:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

down-prod:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml down

build-prod:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# === Self-Hosted ===
up-selfhosted:
	docker compose -f docker-compose.yml -f docker-compose.selfhosted.yml up -d

down-selfhosted:
	docker compose -f docker-compose.yml -f docker-compose.selfhosted.yml down

# === Backup & Restore ===
backup:
	bash scripts/backup.sh

restore:
	@if [ -z "$(ts)" ]; then echo "Usage: make restore ts=<timestamp>"; bash scripts/restore.sh; exit 1; fi
	bash scripts/restore.sh $(ts)

# === Pre-flight ===
preflight:
	bash scripts/preflight-check.sh

ensure-admin:
	@if [ -z "$(email)" ]; then echo "Usage: make ensure-admin email=you@example.com"; exit 1; fi
	docker compose exec -T api python -m app.cli ensure-admin --email "$(email)"

logs:
	docker compose logs -f

logs-api:
	docker compose logs -f api

logs-worker:
	docker compose logs -f worker

# === Database ===
migrate:
	docker compose exec api alembic upgrade head

migration:
	@read -p "Migration message: " msg; \
	docker compose exec api alembic revision --autogenerate -m "$$msg"

db:
	docker compose exec db psql -U studyaio -d studyaio

# === Testing ===
# One command from a clean clone: `make test`. It builds services/app/.venv on
# first use (scripts/bootstrap.sh, constrained by requirements.lock.txt) and runs
# every host-runnable tier with that venv's interpreter, never whatever is on PATH.
# Covers unit + golden + contracts. Integration needs Postgres + Redis and stays a
# separate command: `make test-integration`. pytest exits 5 on an empty collection
# and make propagates it, so a mis-pointed path fails instead of passing.
PYTHON := $(CURDIR)/services/app/.venv/bin/python
VENV_STAMP := services/app/.venv/.bootstrap-stamp
TEST_PATHS ?= tests/unit tests/golden tests/contracts
# The unit-tier coverage gate (75, from pyproject's fail_under) applies only to the
# default full run. Coverage of a hand-picked subset is meaningless and would fail
# every targeted run, so overriding TEST_PATHS turns it off. Pass COV_ARGS
# explicitly to keep it: make test TEST_PATHS=... COV_ARGS="--cov=app".
# A test failure still wins: pytest reports it and exits 1 before any coverage check.
ifeq ($(origin TEST_PATHS),file)
COV_ARGS ?= --cov=app --cov-report=term-missing
endif

bootstrap: $(VENV_STAMP)

$(VENV_STAMP): services/app/requirements.txt services/app/requirements.lock.txt scripts/bootstrap.sh
	bash scripts/bootstrap.sh

# `make test` = the unit/golden/contracts run above, then (default full run only) the
# floor tier via `make test-floor`. The floor tier is a SEPARATE pytest process with
# its own coverage settings: it is mostly static (AST) checks, so `--cov=app` would be
# meaningless for it, while folding it into the unit run would let its numbers leak
# into the unit gate. A targeted TEST_PATHS run skips it, like the unit gate.
test: bootstrap
	cd services/app && $(PYTHON) -m pytest $(TEST_PATHS) -x -v $(COV_ARGS)
ifeq ($(origin TEST_PATHS),file)
	$(MAKE) test-floor
endif

test-unit: bootstrap
	cd services/app && $(PYTHON) -m pytest tests/unit -x -v

# Floor tier (tests/safety, the four floors in docs/strategy.md). It measures its OWN
# guard code (--cov=tests/safety), not `app`, and the 95 comes from pyproject's
# [tool.studyaio.coverage-tiers].floor via scripts/coverage-tier.py. The explicit
# --cov-fail-under overrides pyproject's [tool.coverage.report] fail_under = 75.
# Do not use dotted --cov=app.x sources: they import `app` before the root conftest
# pins DATA_DIR.
test-floor: bootstrap
	cd services/app && $(PYTHON) -m pytest tests/safety -v --cov=tests/safety --cov-report=term-missing --cov-fail-under=$$($(PYTHON) ../../scripts/coverage-tier.py floor)

# Integration tests need a real Postgres + Redis, addressed by DATABASE_URL /
# DATABASE_URL_SYNC / REDIS_URL. Those must be exported before pytest starts —
# the app builds its engine and Redis client at import time (issue #56) — so the
# script starts throwaway containers, exports them, runs pytest and cleans up.
# Pass extra pytest args with: make test-integration ARGS="-k test_health"
test-integration:
	bash scripts/test-integration.sh $(ARGS)

test-golden: bootstrap
	cd services/app && $(PYTHON) -m pytest tests/golden -x -v

# Playwright suite. Needs the stack running (`make up`) — it drives the UI on
# :3001 and seeds data through the API on :8000.
test-e2e:
	cd services/ui && npm run test:e2e

coverage: bootstrap
	cd services/app && $(PYTHON) -m pytest tests/unit --cov=app --cov-report=term-missing

# === Linting ===
lint-python:
	cd services/app && ruff check .

lint-python-fix:
	cd services/app && ruff check --fix . && ruff format .

# === Development ===
shell:
	docker compose exec api bash

worker-shell:
	docker compose exec worker bash

# === Utilities ===
status:
	@echo "=== Docker Services ==="
	@docker compose ps
	@echo ""
	@echo "=== Database ==="
	@docker compose exec db pg_isready -U studyaio 2>/dev/null && echo "Postgres: ready" || echo "Postgres: not ready"
	@echo ""
	@echo "=== Redis ==="
	@docker compose exec redis redis-cli ping 2>/dev/null || echo "Redis: not ready"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# === Pipeline ===
ingest:
	@if [ -z "$(path)" ]; then echo "Usage: make ingest path=<file>"; exit 1; fi
	@FNAME=$$(basename "$(path)") && \
	cp "$(path)" data/uploads/ 2>/dev/null || true && \
	docker compose exec worker python -c \
	  "from app.pipeline.orchestrator import run_pipeline; \
	   r = run_pipeline('/app/data/uploads/'+'$$FNAME'); \
	   print('Pipeline dispatched:', r.id)"

# === v0 Compatibility ===
import-v0:
	DATABASE_URL="postgresql+asyncpg://studyaio:studyaio@localhost:5433/studyaio" \
	python scripts/import_v0.py

seed:
	DATABASE_URL="postgresql+asyncpg://studyaio:studyaio@localhost:5433/studyaio" \
	python scripts/seed_fixtures.py

seed-demo:
	DATABASE_URL="postgresql+asyncpg://studyaio:studyaio@localhost:5433/studyaio" \
	python scripts/seed_demo.py

seed-achievements:
	DATABASE_URL="postgresql+asyncpg://studyaio:studyaio@localhost:5433/studyaio" \
	python scripts/seed_achievements.py

reset-db:
	docker compose exec db psql -U studyaio -d studyaio -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	docker compose exec api alembic upgrade head

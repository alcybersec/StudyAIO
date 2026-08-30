.PHONY: up down logs test test-unit test-integration test-golden test-e2e migrate shell db status build clean ingest import-v0 seed seed-demo lint-python lint-python-fix coverage up-prod down-prod build-prod up-selfhosted down-selfhosted backup restore preflight

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
test:
	cd services/app && pytest -x -v

test-unit:
	cd services/app && pytest tests/unit -x -v

test-integration:
	cd services/app && pytest tests/integration -x -v

test-golden:
	cd services/app && pytest tests/golden -x -v

# Playwright suite. Needs the stack running (`make up`) — it drives the UI on
# :3001 and seeds data through the API on :8000.
test-e2e:
	cd services/ui && npm run test:e2e

coverage:
	cd services/app && pytest tests/unit --cov=app --cov-report=term-missing --cov-fail-under=70

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

# Rules for infra/ and Docker files

## Docker Compose
- All services must be startable with `docker compose up -d`
- Services must have health checks where applicable
- Use named volumes for data persistence (not bind mounts for database data)
- Use bind mounts only for: source code (dev), data/ directory, config files
- Pin all image versions (e.g., `pgvector/pgvector:pg16`, not `pgvector/pgvector:latest`)
- Environment variables with sensible defaults in docker-compose.yml
- Sensitive values use .env file (never committed)

## Dockerfiles
- Use multi-stage builds for the UI (build stage + nginx serve stage)
- Backend Dockerfile: `python:3.12-slim` base
- Install system dependencies first (cache layer), then pip install (cache layer), then copy source
- Run as non-root user in production
- Include .dockerignore to minimize context

## Database
- Schema initialization in `infra/db/init.sql` (only for extensions like pgvector)
- All table creation via Alembic migrations, NOT in init.sql
- pgvector extension enabled in init.sql: `CREATE EXTENSION IF NOT EXISTS vector;`
- Connection pooling: let SQLAlchemy handle it, don't add pgbouncer in v1

## Networking
- Services communicate via Docker Compose service names (e.g., `db:5432`, `redis:6379`)
- Only expose ports that need external access: ui (3000), api (8000)
- Database and Redis ports exposed in dev only, not in production compose

## Data Volumes
- `data/uploads/` — immutable after write (original files, never modified)
- `data/extractions/` — regeneratable (can be rebuilt from uploads)
- `data/summaries/` — regeneratable (can be rebuilt from extractions)
- PostgreSQL data — critical (this is the source of truth)
- Redis data — ephemeral (task queue, can be lost without data loss)

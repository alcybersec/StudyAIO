---
name: docker-ops
description: Manage Docker Compose services for StudyAIO. Use when starting/stopping services, debugging container issues, checking service health, or modifying Docker configuration.
---

# Docker Operations

## Quick Reference

```bash
# Start everything
docker compose up -d

# Check status
docker compose ps

# View logs (follow)
docker compose logs -f api worker

# Restart a single service
docker compose restart worker

# Rebuild after code changes
docker compose build api && docker compose up -d api

# Full rebuild (no cache)
docker compose build --no-cache

# Connect to database
docker compose exec db psql -U studyaio -d studyaio

# Run migrations
docker compose exec api alembic upgrade head

# Open shell in API container
docker compose exec api bash

# Stop everything
docker compose down

# Stop and remove volumes (DESTRUCTIVE — deletes database)
docker compose down -v
```

## Debugging Container Issues

1. **Service won't start:** Check `docker compose logs <service>` for error messages
2. **Database connection refused:** Wait for health check — `docker compose exec db pg_isready`
3. **Redis connection refused:** Check `docker compose exec redis redis-cli ping`
4. **Worker not processing tasks:** Check `docker compose logs worker` and verify Redis is up
5. **Port already in use:** Check `lsof -i :<port>` and stop conflicting process

## Service Dependencies

```
ui → api → db, redis
worker → db, redis
```

Always start in order: db, redis → api, worker → ui.
Docker Compose handles this via `depends_on` but health checks ensure readiness.

## Environment Variables

Defined in `.env` (never committed) and loaded by Docker Compose.
Template in `.env.example`.

#!/usr/bin/env bash
#
# Run the integration suite the same way CI does.
#
# The integration tests need a real Postgres (with pgvector) and a real Redis,
# addressed by DATABASE_URL / DATABASE_URL_SYNC / REDIS_URL. Those variables have
# to exist *before* pytest starts, because app.config.settings, the SQLAlchemy
# engine and the Redis client are all built at import time and never re-read the
# environment afterwards (issue #56).
#
# This script starts throwaway containers, exports the three variables, runs
# pytest, and removes the containers again on the way out.
#
# Usage:
#   scripts/test-integration.sh                  # whole suite
#   scripts/test-integration.sh -k test_health   # extra args go to pytest
#
# If DATABASE_URL is already set (CI, or your own long-lived services), no
# containers are started and your environment is used as-is.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$REPO_ROOT/services/app"

PG_IMAGE="${PG_IMAGE:-pgvector/pgvector:pg16}"
REDIS_IMAGE="${REDIS_IMAGE:-redis:7-alpine}"
PG_NAME="studyaio-itest-postgres-$$"
REDIS_NAME="studyaio-itest-redis-$$"

# Same values CI uses, so both paths are identical.
PG_USER=testuser
PG_PASSWORD=testpass
PG_DB=testdb

STARTED_CONTAINERS=()

cleanup() {
    if [ "${#STARTED_CONTAINERS[@]}" -gt 0 ]; then
        echo "==> Removing test containers"
        docker rm -f "${STARTED_CONTAINERS[@]}" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT INT TERM

wait_for() {
    local name="$1" desc="$2"
    shift 2
    for _ in $(seq 1 60); do
        if docker exec "$name" "$@" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    echo "ERROR: $desc did not become ready within 60s" >&2
    docker logs "$name" >&2 || true
    return 1
}

# Host port Docker picked for a container's exposed port, e.g. "0.0.0.0:49154".
host_port() {
    docker port "$1" "$2" | head -n1 | sed 's/.*://'
}

if [ -n "${DATABASE_URL:-}" ]; then
    echo "==> DATABASE_URL is already set; using the existing services"
else
    echo "==> Starting Postgres ($PG_IMAGE)"
    docker run -d --name "$PG_NAME" \
        -e POSTGRES_USER="$PG_USER" \
        -e POSTGRES_PASSWORD="$PG_PASSWORD" \
        -e POSTGRES_DB="$PG_DB" \
        -p 127.0.0.1::5432 \
        "$PG_IMAGE" >/dev/null
    STARTED_CONTAINERS+=("$PG_NAME")

    echo "==> Starting Redis ($REDIS_IMAGE)"
    docker run -d --name "$REDIS_NAME" -p 127.0.0.1::6379 "$REDIS_IMAGE" >/dev/null
    STARTED_CONTAINERS+=("$REDIS_NAME")

    wait_for "$PG_NAME" "Postgres" pg_isready -U "$PG_USER" -d "$PG_DB"
    wait_for "$REDIS_NAME" "Redis" redis-cli ping

    PG_PORT="$(host_port "$PG_NAME" 5432/tcp)"
    REDIS_PORT="$(host_port "$REDIS_NAME" 6379/tcp)"

    export DATABASE_URL="postgresql+asyncpg://$PG_USER:$PG_PASSWORD@127.0.0.1:$PG_PORT/$PG_DB"
    export DATABASE_URL_SYNC="postgresql://$PG_USER:$PG_PASSWORD@127.0.0.1:$PG_PORT/$PG_DB"
    export REDIS_URL="redis://127.0.0.1:$REDIS_PORT/0"

    echo "==> Postgres on 127.0.0.1:$PG_PORT, Redis on 127.0.0.1:$REDIS_PORT"
fi

# Prefer an explicit $PYTEST, then the project venv, then whatever is on PATH —
# so `make test-integration` works without activating anything first.
if [ -n "${PYTEST:-}" ]; then
    :
elif [ -x "$APP_DIR/.venv/bin/pytest" ]; then
    PYTEST="$APP_DIR/.venv/bin/pytest"
elif command -v pytest >/dev/null 2>&1; then
    PYTEST="pytest"
else
    echo "ERROR: pytest not found. Activate the virtualenv, or set PYTEST=/path/to/pytest." >&2
    exit 1
fi

cd "$APP_DIR"
if [ "$#" -gt 0 ]; then
    pytest_args=("$@")
else
    pytest_args=(-x -v)
fi

echo "==> Running: $PYTEST tests/integration ${pytest_args[*]}"
"$PYTEST" tests/integration "${pytest_args[@]}"

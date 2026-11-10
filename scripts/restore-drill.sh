#!/usr/bin/env bash
# Restore drill: prove a backup restores, without touching the live stack.  [M35-W1-08]
#
#   scripts/restore-drill.sh <backups-dir | path/to/studyaio_<ts>_db.sql.gz> [timestamp]
#
# The argument is normally a fresh `restic restore` of the OFF-HOST copy (that is
# what proves the off-site path), or ./backups. Given a directory, the newest
# studyaio_*_db.sql.gz under it is used unless a timestamp is named; given a dump
# file, its sibling studyaio_<ts>_data.tar.gz is used if present.
#
# The drill:
#   1. starts a throwaway Postgres+pgvector on an --internal docker network (no
#      host ports, no internet, tmpfs storage), named studyaio-drill-<pid>;
#   2. loads the dump with ON_ERROR_STOP in a single transaction;
#   3. runs `alembic upgrade head` from the pinned api image against it (proves
#      the dump is compatible with the code that would run after a restore);
#   4. counts rows in the core tables and lists the data archive;
#   5. prints one summary line with the elapsed time and, when the node_exporter
#      textfile directory is writable, writes a metric;
#   6. removes its container and network (always).
# It never connects to the live database and never reads or writes data/.
#
# Environment:
#   API_IMAGE   pinned api image to run alembic from (default: the image of the
#               running api container; the drill exits 1 if neither is known)
#   PG_IMAGE    Postgres image (default: the pgvector image of docker-compose.yml)
#   DRILL_ALLOW_EMPTY=1   accept a restored database with zero users
#   TEXTFILE_DIR          node_exporter textfile directory
#
# Timing note: total_s covers dump load + migration + counts. Add the time to
# fetch the off-host copy and (for a real restore) to extract data/ for the RTO.
set -euo pipefail

SRC="${1:?usage: $0 <backups-dir | db-dump.sql.gz> [timestamp]}"
TS="${2:-}"
PROJECT="studyaio-drill-$$"
TEXTFILE_DIR="${TEXTFILE_DIR:-/var/lib/node_exporter/textfile_collector}"
start="$(date +%s)"

DUMP=""
DATA=""
if [[ -f "$SRC" ]]; then
    DUMP="$SRC"
    base="$(basename "$SRC")"
    [[ "$base" =~ ^studyaio_([0-9]{8}_[0-9]{6})_db\.sql\.gz$ ]] \
        || { echo "not a studyaio_<ts>_db.sql.gz file: ${SRC}" >&2; exit 1; }
    TS="${BASH_REMATCH[1]}"
    [[ -f "$(dirname "$SRC")/studyaio_${TS}_data.tar.gz" ]] && DATA="$(dirname "$SRC")/studyaio_${TS}_data.tar.gz"
elif [[ -d "$SRC" ]]; then
    if [[ -z "$TS" ]]; then
        newest="$(find "$SRC" -name 'studyaio_*_db.sql.gz' -printf '%T@ %p\n' | sort -nr | head -n 1 | cut -d' ' -f2-)"
        [[ -n "$newest" ]] || { echo "no studyaio_*_db.sql.gz under ${SRC}" >&2; exit 1; }
        TS="$(basename "$newest" _db.sql.gz)"
        TS="${TS#studyaio_}"
    fi
    [[ "$TS" =~ ^[0-9]{8}_[0-9]{6}$ ]] || { echo "timestamp must look like 20260310_020000" >&2; exit 1; }
    DUMP="$(find "$SRC" -name "studyaio_${TS}_db.sql.gz" | head -n 1)"
    DATA="$(find "$SRC" -name "studyaio_${TS}_data.tar.gz" | head -n 1)"
else
    echo "not a file or directory: ${SRC}" >&2
    exit 1
fi
[[ -f "$DUMP" ]] || { echo "dump for ${TS} not found under ${SRC}" >&2; exit 1; }
gunzip -t "$DUMP" || { echo "dump is corrupted: ${DUMP}" >&2; exit 1; }
# A pg_dump cut short still gunzips; only the trailer proves it ran to the end.
zcat "$DUMP" | tail -n 5 | grep -q '^-- PostgreSQL database dump complete' \
    || { echo "dump has no 'PostgreSQL database dump complete' trailer (truncated?): ${DUMP}" >&2; exit 1; }
[[ -z "$DATA" ]] || tar tzf "$DATA" >/dev/null || { echo "data archive is corrupted: ${DATA}" >&2; exit 1; }
echo "==> Drill on backup ${TS}"

PG_IMAGE="${PG_IMAGE:-$(docker compose -f docker-compose.yml config --images | grep -m1 pgvector || true)}"
[[ -n "$PG_IMAGE" ]] || { echo "cannot determine the Postgres image (set PG_IMAGE)" >&2; exit 1; }
API_IMAGE="${API_IMAGE:-$(docker ps --filter label=com.docker.compose.service=api --format '{{.Image}}' | head -n 1)}"
[[ -n "$API_IMAGE" ]] || { echo "cannot determine the pinned api image (set API_IMAGE)" >&2; exit 1; }

# The dump names the production role as owner of every object; run the scratch
# server as that role so the dump loads unmodified.
OWNER="$({ gunzip -c "$DUMP" | grep -m1 -oE ' OWNER TO [a-z_][a-z0-9_]*;' | sed -E 's/ OWNER TO (.*);/\1/'; } || true)"
OWNER="${OWNER:-studyaio}"

cleanup() {
    docker rm -f "${PROJECT}-db" >/dev/null 2>&1 || true
    docker network rm "${PROJECT}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker network create --internal "${PROJECT}" >/dev/null
docker run -d --name "${PROJECT}-db" --network "${PROJECT}" --network-alias db \
    --tmpfs /var/lib/postgresql/data \
    -e "POSTGRES_USER=${OWNER}" -e POSTGRES_PASSWORD=drill -e POSTGRES_DB=drill \
    "$PG_IMAGE" >/dev/null
ready=0
for _ in $(seq 1 60); do
    if docker exec "${PROJECT}-db" pg_isready -U "$OWNER" -d drill >/dev/null 2>&1; then ready=1; break; fi
    sleep 1
done
[[ "$ready" -eq 1 ]] || { echo "scratch database did not become ready" >&2; exit 1; }
# pg_isready answers during init, before the entrypoint restarts the server for
# real; wait for a query to succeed.
for _ in $(seq 1 30); do
    docker exec "${PROJECT}-db" psql -U "$OWNER" -d drill -qAt -c 'SELECT 1' >/dev/null 2>&1 && break
    sleep 1
done

echo "==> Loading dump"
gunzip -c "$DUMP" \
    | docker exec -i "${PROJECT}-db" psql -v ON_ERROR_STOP=1 --single-transaction -U "$OWNER" -d drill -q >/dev/null
loaded="$(date +%s)"

echo "==> alembic upgrade head with ${API_IMAGE%@*}"
docker run --rm --network "${PROJECT}" \
    -e "DATABASE_URL=postgresql+asyncpg://${OWNER}:drill@db:5432/drill" \
    -e "DATABASE_URL_SYNC=postgresql://${OWNER}:drill@db:5432/drill" \
    -e REDIS_URL=redis://unused:6379/0 \
    "$API_IMAGE" alembic upgrade head

echo "==> Row counts"
counts="$(docker exec "${PROJECT}-db" psql -U "$OWNER" -d drill -At -F= -c "
  SELECT 'users', count(*) FROM users UNION ALL
  SELECT 'courses', count(*) FROM courses UNION ALL
  SELECT 'lecture_artifacts', count(*) FROM lecture_artifacts UNION ALL
  SELECT 'summaries', count(*) FROM summaries UNION ALL
  SELECT 'chunks', count(*) FROM chunks;")"
echo "$counts" | sed 's/^/    /'
users="$(echo "$counts" | sed -n 's/^users=//p')"
if [[ "${users:-0}" -le 0 && "${DRILL_ALLOW_EMPTY:-0}" != "1" ]]; then
    echo "drill FAILED: restored database has no users" >&2
    exit 1
fi

files=0
if [[ -n "$DATA" ]]; then
    files="$(tar tzf "$DATA" | grep -cv '/$' || true)"
    echo "    data archive: ${files} files"
fi
end="$(date +%s)"

echo "restore_drill ok backup=${TS} users=${users:-0} data_files=${files} load_s=$((loaded - start)) total_s=$((end - start))"
if [[ -d "$TEXTFILE_DIR" && -w "$TEXTFILE_DIR" ]]; then
    tmp="$(mktemp "${TEXTFILE_DIR}/.studyaio_drill.XXXXXX")"
    printf '# TYPE studyaio_restore_drill_last_success_timestamp_seconds gauge\nstudyaio_restore_drill_last_success_timestamp_seconds %s\n# TYPE studyaio_restore_drill_duration_seconds gauge\nstudyaio_restore_drill_duration_seconds %s\n' \
        "$end" "$((end - start))" > "$tmp"
    chmod 644 "$tmp"
    mv "$tmp" "${TEXTFILE_DIR}/studyaio_drill.prom"
fi

#!/usr/bin/env bash
# StudyAIO -- database & data restore.  [M35-W1-08]
#
# Usage: bash scripts/restore.sh                 # list available backups, exit 1
#        bash scripts/restore.sh <timestamp> [--yes]
#   e.g.: bash scripts/restore.sh 20260310_020000
#
# Restores files written by scripts/backup.sh (studyaio_<ts>_db.sql.gz and
# studyaio_<ts>_data.tar.gz). Safety properties:
#   - drives the SAME compose files as the running stack (so the prod overlay on
#     prod), taken from the api container's compose labels or from
#     STUDYAIO_COMPOSE_FILES; with neither it exits 1 rather than guess;
#   - validates the timestamp and both files before touching anything;
#   - takes a safety dump of the current database first and aborts if it fails;
#   - restores with ON_ERROR_STOP in ONE transaction that also drops the old
#     schema, so a bad dump rolls back and leaves the current database intact;
#   - never deletes data/: the current tree is renamed to data.prerestore-<ts>
#     after the archive has been extracted beside it. The operator removes the
#     old tree by hand once the restore is verified.
# Environment: BACKUP_DIR (default ./backups), DATA_DIR (default ./data),
#              STUDYAIO_COMPOSE_FILES (space separated).

set -euo pipefail
# The safety dump holds the whole database: owner-only.
umask 077

BACKUP_DIR="${BACKUP_DIR:-./backups}"
DATA_DIR="${DATA_DIR:-./data}"
NOW="$(date +%Y%m%d_%H%M%S)"

RED='\033[0;31m'; GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; NC='\033[0m'
info() { echo -e "${BLUE}[INFO]${NC} $*"; }
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }

list_backups() {
    echo "Available backups:"
    if ls "$BACKUP_DIR"/studyaio_*_db.sql.gz 1>/dev/null 2>&1; then
        ls -1t "$BACKUP_DIR"/studyaio_*_db.sql.gz | while read -r f; do
            BASE="$(basename "$f" _db.sql.gz)"
            echo "  ${BASE#studyaio_}  ($(du -h "$f" | cut -f1))"
        done
    else
        echo "  (no backups found in $BACKUP_DIR)"
    fi
}

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <timestamp> [--yes]"
    echo ""
    list_backups
    exit 1
fi
TIMESTAMP="$1"
ASSUME_YES="${2:-}"
[[ "$TIMESTAMP" =~ ^[0-9]{8}_[0-9]{6}$ ]] || { err "timestamp must look like 20260310_020000"; exit 1; }

DB_DUMP="${BACKUP_DIR}/studyaio_${TIMESTAMP}_db.sql.gz"
DATA_TAR="${BACKUP_DIR}/studyaio_${TIMESTAMP}_data.tar.gz"

# -- Which compose files? The running stack's, never a guess ----------------

compose_files() {
    if [[ -n "${STUDYAIO_COMPOSE_FILES:-}" ]]; then
        echo "$STUDYAIO_COMPOSE_FILES"
        return
    fi
    local id
    id="$(docker ps -q --filter "label=com.docker.compose.project.working_dir=${PWD}" \
                       --filter "label=com.docker.compose.service=api" | head -n 1)"
    [[ -n "$id" ]] || return 1
    # Label value: absolute, comma-separated paths.
    docker inspect -f '{{index .Config.Labels "com.docker.compose.project.config_files"}}' "$id" | tr ',' ' '
}
if ! FILES="$(compose_files)" || [[ -z "${FILES// /}" ]]; then
    err "Cannot tell which compose files the stack uses (api is not running here)."
    err "Set STUDYAIO_COMPOSE_FILES, e.g. STUDYAIO_COMPOSE_FILES=\"docker-compose.yml docker-compose.prod.yml\""
    exit 1
fi
COMPOSE=(docker compose)
read -ra FILE_LIST <<< "$FILES"
for f in "${FILE_LIST[@]}"; do COMPOSE+=(-f "$f"); done
info "Compose: ${COMPOSE[*]}"

# -- Validate backup files ----------------------------------------------------

[[ -f "$DB_DUMP" ]] || { err "Database dump not found: $DB_DUMP"; list_backups; exit 1; }
info "Database dump: $DB_DUMP ($(du -h "$DB_DUMP" | cut -f1))"
gunzip -t "$DB_DUMP" || { err "Dump file is corrupted -- aborting"; exit 1; }
if [[ -f "$DATA_TAR" ]]; then
    info "Data archive: $DATA_TAR ($(du -h "$DATA_TAR" | cut -f1))"
    tar tzf "$DATA_TAR" >/dev/null || { err "Data archive is corrupted -- aborting"; exit 1; }
else
    warn "No data archive for this timestamp -- only the database will be restored"
fi
ok "Backup files verified"

echo ""
warn "This REPLACES the current database with the backup from $TIMESTAMP."
warn "A safety dump is taken first; data/ is moved aside, never deleted."
if [[ "$ASSUME_YES" != "--yes" ]]; then
    read -rp "Type the timestamp to confirm: " CONFIRM
    [[ "$CONFIRM" == "$TIMESTAMP" ]] || { info "Restore cancelled"; exit 0; }
fi

# -- Safety dump of what is there now -----------------------------------------

PRE="${BACKUP_DIR}/prerestore_${NOW}.sql.gz"
info "Taking a safety dump of the current database: $PRE"
mkdir -p "$BACKUP_DIR"
"${COMPOSE[@]}" up -d --no-build --wait db
# shellcheck disable=SC2016  # $POSTGRES_* expand inside the db container
if ! "${COMPOSE[@]}" exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "${PRE}.partial" \
        || [[ "$(stat -c %s "${PRE}.partial")" -lt 100 ]] || ! gzip -t "${PRE}.partial"; then
    rm -f "${PRE}.partial"
    err "Safety dump failed -- nothing was changed"
    exit 1
fi
mv "${PRE}.partial" "$PRE"
ok "Safety dump written"

# -- Stage the data archive (before the database is touched) ------------------

PARENT="$(cd "$(dirname "$DATA_DIR")" && pwd)"
NAME="$(basename "$DATA_DIR")"
STAGE="${NAME}.restore-${NOW}"
SWAP_DATA=0
TOOL_IMAGE=""
if [[ -f "$DATA_TAR" ]]; then
    info "Extracting data archive into ${PARENT}/${STAGE} (numeric owners preserved)..."
    # As root in a throwaway container, so uid/gid from the archive survive; the
    # host user could not chown them back. Uses the already-present db image.
    TOOL_IMAGE="$("${COMPOSE[@]}" config --images | grep -m1 pgvector || true)"
    [[ -n "$TOOL_IMAGE" ]] || { err "cannot find the db image for the extract step"; exit 1; }
    mkdir -p "${PARENT}/${STAGE}"
    docker run --rm -v "$(cd "$BACKUP_DIR" && pwd):/backups:ro" -v "${PARENT}:/parent" \
        --entrypoint tar "$TOOL_IMAGE" \
        --numeric-owner -xzpf "/backups/$(basename "$DATA_TAR")" -C "/parent/${STAGE}"
    [[ -d "${PARENT}/${STAGE}/${NAME}" ]] || {
        err "archive did not contain ${NAME}/ -- current data and database left untouched (staging: ${PARENT}/${STAGE})"
        exit 1
    }
    SWAP_DATA=1
fi

# -- Restore database ---------------------------------------------------------

info "Stopping application services (db stays up)..."
"${COMPOSE[@]}" config --services | grep -vx db | xargs "${COMPOSE[@]}" stop

info "Restoring database (one transaction; any SQL error rolls everything back)..."
# The schema drop is inside the same transaction as the load, so a failing dump
# leaves the current database exactly as it was.
# shellcheck disable=SC2016
{ echo 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'; gunzip -c "$DB_DUMP"; } \
    | "${COMPOSE[@]}" exec -T db sh -c 'psql -v ON_ERROR_STOP=1 --single-transaction -U "$POSTGRES_USER" -d "$POSTGRES_DB" --quiet'
ok "Database restored (previous state: $PRE)"

# -- Swap the data tree: rename aside, never delete ---------------------------

if [[ "$SWAP_DATA" -eq 1 ]]; then
    docker run --rm -v "${PARENT}:/parent" --entrypoint sh "$TOOL_IMAGE" -c '
        set -e
        cd /parent
        mv "$1" "$1.prerestore-$3"
        mv "$2/$1" "$1"
        rmdir "$2"' sh "$NAME" "$STAGE" "$NOW"
    ok "data/ restored; previous tree kept at ${NAME}.prerestore-${NOW}"
fi

# -- Migrate and restart --------------------------------------------------------

info "Running migrations (one-off container of the stack's api image)..."
"${COMPOSE[@]}" run --rm --no-deps -T api alembic upgrade head

info "Starting all services..."
"${COMPOSE[@]}" up -d --no-build

info "Waiting for /health/ready..."
for i in $(seq 1 24); do
    if "${COMPOSE[@]}" exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready', timeout=5)" >/dev/null 2>&1; then
        ok "api ready after ~$((i * 5))s"
        break
    fi
    if [[ "$i" -eq 24 ]]; then
        err "api not ready after 120s -- see logs; the safety dump is $PRE"
        exit 1
    fi
    sleep 5
done

echo ""
ok "Restore complete from backup: $TIMESTAMP"
echo "  Safety dump of the replaced database: $PRE"
if [[ "$SWAP_DATA" -eq 1 ]]; then
    echo "  Previous data tree: ${PARENT}/${NAME}.prerestore-${NOW} (remove by hand once verified)"
fi

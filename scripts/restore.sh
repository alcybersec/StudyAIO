#!/usr/bin/env bash
# StudyAIO — Database & data restore script
#
# Usage: bash scripts/restore.sh <timestamp>
#   e.g.: bash scripts/restore.sh 20260310_020000
#
# Restores from backup files created by backup.sh.
# WARNING: This will overwrite the current database!

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${BLUE}[INFO]${NC} $*"; }
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }

# ── Parse arguments ──────────────────────────────────────────────

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <timestamp>"
    echo ""
    echo "Available backups:"
    if ls "$BACKUP_DIR"/studyaio_*_db.sql.gz 1>/dev/null 2>&1; then
        ls -1t "$BACKUP_DIR"/studyaio_*_db.sql.gz | while read -r f; do
            BASE=$(basename "$f" _db.sql.gz)
            TS=${BASE#studyaio_}
            SIZE=$(du -h "$f" | cut -f1)
            echo "  $TS  ($SIZE)"
        done
    else
        echo "  (no backups found in $BACKUP_DIR)"
    fi
    exit 1
fi

TIMESTAMP="$1"
DB_DUMP="${BACKUP_DIR}/studyaio_${TIMESTAMP}_db.sql.gz"
DATA_TAR="${BACKUP_DIR}/studyaio_${TIMESTAMP}_data.tar.gz"

# ── Validate backup files ────────────────────────────────────────

if [[ ! -f "$DB_DUMP" ]]; then
    err "Database dump not found: $DB_DUMP"
    exit 1
fi

info "Found database dump: $DB_DUMP ($(du -h "$DB_DUMP" | cut -f1))"

if [[ -f "$DATA_TAR" ]]; then
    info "Found data archive: $DATA_TAR ($(du -h "$DATA_TAR" | cut -f1))"
else
    warn "No data archive found for this timestamp — only restoring database"
fi

# ── Verify dump integrity ────────────────────────────────────────

info "Verifying dump integrity..."
if ! gunzip -t "$DB_DUMP" 2>/dev/null; then
    err "Dump file is corrupted — aborting"
    exit 1
fi
ok "Dump integrity verified"

# ── Confirmation ──────────────────────────────────────────────────

echo ""
warn "This will OVERWRITE the current database with backup from $TIMESTAMP."
read -rp "Are you sure? (yes/no): " CONFIRM
if [[ "$CONFIRM" != "yes" ]]; then
    info "Restore cancelled"
    exit 0
fi

# ── Restore database ─────────────────────────────────────────────

info "Stopping application services..."
docker compose stop api worker beat 2>/dev/null || true

info "Restoring database from $DB_DUMP..."
gunzip -c "$DB_DUMP" | docker compose exec -T db psql -U "${POSTGRES_USER:-studyaio}" -d "${POSTGRES_DB:-studyaio}" --quiet -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" 2>/dev/null || true
gunzip -c "$DB_DUMP" | docker compose exec -T db psql -U "${POSTGRES_USER:-studyaio}" -d "${POSTGRES_DB:-studyaio}" --quiet
ok "Database restored"

# ── Restore data directory ────────────────────────────────────────

DATA_DIR="${DATA_DIR:-./data}"

if [[ -f "$DATA_TAR" ]]; then
    info "Restoring data directory from $DATA_TAR..."
    tar xzf "$DATA_TAR" -C "$(dirname "$DATA_DIR")"
    ok "Data directory restored"
fi

# ── Restart services ──────────────────────────────────────────────

info "Running database migrations..."
docker compose start api 2>/dev/null || docker compose up -d api
sleep 3
docker compose exec api alembic upgrade head

info "Starting all services..."
docker compose start worker beat 2>/dev/null || docker compose up -d worker beat

echo ""
ok "Restore complete from backup: $TIMESTAMP"
echo "  Database: restored"
[[ -f "$DATA_TAR" ]] && echo "  Data:     restored"
echo ""
info "Verify the application is working correctly."

#!/usr/bin/env bash
# StudyAIO — Database & data backup script
#
# Usage (standalone): bash scripts/backup.sh
# Usage (Docker):     docker compose run backup /backup.sh
#
# Backs up the Postgres database and the data/ directory.
# Keeps the last N backups (default: 7).

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION="${BACKUP_RETENTION:-7}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="studyaio_${TIMESTAMP}"

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${BLUE}[INFO]${NC} $*"; }
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# A dead or unresolvable DB host must fail the run, not hang the Celery slot.
export PGCONNECT_TIMEOUT="${PGCONNECT_TIMEOUT:-15}"

mkdir -p "$BACKUP_DIR"

# ── Database dump ──────────────────────────────────────────────────

DB_DUMP="${BACKUP_DIR}/${BACKUP_NAME}_db.sql.gz"

info "Dumping database..."
# Dump to a .partial name and rename only on success, so a failed run (pipefail
# makes a pg_dump error fail the pipeline) can never leave a file that retention
# or restore would mistake for a backup.
if [[ -n "${PGHOST:-}" ]]; then
    # Inside the worker container (run_backup) or a sidecar: libpq reads
    # PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE from the environment.
    command -v pg_dump >/dev/null || { err "pg_dump not found in PATH"; exit 1; }
    pg_dump | gzip > "${DB_DUMP}.partial" || { err "pg_dump failed"; rm -f "${DB_DUMP}.partial"; exit 1; }
else
    # Running on host — connect via Docker
    docker compose exec -T db pg_dump -U "${POSTGRES_USER:-studyaio}" "${POSTGRES_DB:-studyaio}" | gzip > "${DB_DUMP}.partial" \
        || { err "pg_dump failed"; rm -f "${DB_DUMP}.partial"; exit 1; }
fi
# An empty gzip stream is 20 bytes; a real pg_dump header alone is far larger.
if [[ "$(stat -c %s "${DB_DUMP}.partial")" -lt 100 ]]; then
    err "Database dump is empty"
    rm -f "${DB_DUMP}.partial"
    exit 1
fi
mv "${DB_DUMP}.partial" "$DB_DUMP"
ok "Database dump: $DB_DUMP ($(du -h "$DB_DUMP" | cut -f1))"

# Verify the dump is valid
info "Verifying dump integrity..."
if gunzip -t "$DB_DUMP" 2>/dev/null; then
    ok "Dump integrity verified (gzip valid)"
else
    err "Dump integrity check failed — file may be corrupted"
    exit 1
fi

# ── Data directory archive ─────────────────────────────────────────

DATA_DIR="${DATA_DIR:-./data}"
DATA_TAR="${BACKUP_DIR}/${BACKUP_NAME}_data.tar.gz"

if [[ -d "$DATA_DIR" ]]; then
    info "Archiving data directory..."
    # tar exits 1 when a file changed while being read (live uploads) -- the
    # archive is still usable. Anything higher is a real failure, which this
    # used to swallow with `|| true`.
    rc=0
    tar czf "$DATA_TAR" -C "$(dirname "$DATA_DIR")" "$(basename "$DATA_DIR")" || rc=$?
    if [[ "$rc" -gt 1 ]]; then
        err "Data archive failed (tar exit $rc)"
        rm -f "$DATA_TAR"
        exit 1
    fi
    ok "Data archive: $DATA_TAR ($(du -h "$DATA_TAR" | cut -f1))"
else
    info "No data directory found at $DATA_DIR — skipping"
fi

# ── Retention cleanup ──────────────────────────────────────────────

info "Applying retention policy (keep last $RETENTION backups)..."
# Group by prefix (date_time), count unique timestamps
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/studyaio_*_db.sql.gz 2>/dev/null | wc -l || echo 0)
if [[ "$BACKUP_COUNT" -gt "$RETENTION" ]]; then
    EXCESS=$((BACKUP_COUNT - RETENTION))
    ls -1t "$BACKUP_DIR"/studyaio_*_db.sql.gz | tail -n "$EXCESS" | while read -r f; do
        # Remove both db and data files for this timestamp
        BASE=$(basename "$f" _db.sql.gz)
        rm -f "$BACKUP_DIR/${BASE}_db.sql.gz" "$BACKUP_DIR/${BASE}_data.tar.gz"
        info "Removed old backup: $BASE"
    done
fi

# ── Optional S3 upload ─────────────────────────────────────────────

if [[ -n "${S3_BACKUP_BUCKET:-}" ]]; then
    info "Uploading backups to S3: s3://${S3_BACKUP_BUCKET}/backups/"
    if command -v aws &>/dev/null; then
        aws s3 cp "$DB_DUMP" "s3://${S3_BACKUP_BUCKET}/backups/" --quiet
        [[ -f "$DATA_TAR" ]] && aws s3 cp "$DATA_TAR" "s3://${S3_BACKUP_BUCKET}/backups/" --quiet
        ok "S3 upload complete"
    else
        err "aws CLI not found — S3 upload skipped"
    fi
fi

echo ""
ok "Backup complete: $BACKUP_NAME"
echo "  Database: $DB_DUMP"
[[ -f "$DATA_TAR" ]] && echo "  Data:     $DATA_TAR"

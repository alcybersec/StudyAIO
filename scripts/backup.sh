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

mkdir -p "$BACKUP_DIR"

# ── Database dump ──────────────────────────────────────────────────

DB_DUMP="${BACKUP_DIR}/${BACKUP_NAME}_db.sql.gz"

info "Dumping database..."
if [[ -n "${PGHOST:-}" ]]; then
    # Running inside Docker backup sidecar
    pg_dump | gzip > "$DB_DUMP"
else
    # Running on host — connect via Docker
    docker compose exec -T db pg_dump -U "${POSTGRES_USER:-studyaio}" "${POSTGRES_DB:-studyaio}" | gzip > "$DB_DUMP"
fi
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
    tar czf "$DATA_TAR" -C "$(dirname "$DATA_DIR")" "$(basename "$DATA_DIR")" 2>/dev/null || true
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

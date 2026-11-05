#!/usr/bin/env bash
# Off-host, encrypted, append-only copy of StudyAIO's backups and data/.  [W1-07]
#
# Runs ON THE DEPLOY HOST from a systemd timer (infra/host/studyaio-offsite-backup.*),
# after the nightly in-container dump. Uses restic (client-side encryption,
# content-addressed dedup, so data/ is copied incrementally instead of as a nightly
# tarball). The repository lives on ANOTHER machine; the repository server should
# run append-only (e.g. restic rest-server --append-only), so a compromised prod
# host can add snapshots but not delete or rewrite old ones. Pruning runs on the
# repository side, never from here.
#
# Configuration comes from a root-owned file OUTSIDE the repo, so no host names,
# URLs or passwords are tracked:
#   /etc/studyaio/offsite.conf   (mode 0600)
#     RESTIC_REPOSITORY=rest:https://<backup-host>:<port>/studyaio
#     RESTIC_PASSWORD_FILE=/etc/studyaio/restic.pass
#     # optional: RESTIC_CACERT=/etc/studyaio/backup-ca.pem
#
# Exit status is non-zero on any failure (the systemd unit then shows failed and
# the textfile metric is not refreshed, so the OffsiteBackupStale alert fires).
set -euo pipefail
umask 077

CONF="${STUDYAIO_OFFSITE_CONF:-/etc/studyaio/offsite.conf}"
SRC="${STUDYAIO_DIR:-/opt/studyaio}"
TEXTFILE_DIR="${TEXTFILE_DIR:-/var/lib/node_exporter/textfile_collector}"

[[ -r "$CONF" ]] || { echo "offsite: cannot read ${CONF}" >&2; exit 1; }
# shellcheck source=/dev/null
. "$CONF"
: "${RESTIC_REPOSITORY:?set in ${CONF}}" "${RESTIC_PASSWORD_FILE:?set in ${CONF}}"
export RESTIC_REPOSITORY RESTIC_PASSWORD_FILE
[[ -n "${RESTIC_CACERT:-}" ]] && export RESTIC_CACERT

# Refuse a stale source: if the nightly dump did not run, copying yesterday's
# files again would make the off-site copy look fresh while RPO silently grows.
NEWEST="$(find "${SRC}/backups" -maxdepth 1 -name 'studyaio_*_db.sql.gz' -newermt '-26 hours' -print -quit)"
if [[ -z "$NEWEST" ]]; then
    echo "offsite: no studyaio_*_db.sql.gz newer than 26h in ${SRC}/backups -- is BACKUP_ENABLED on?" >&2
    exit 2
fi

start="$(date +%s)"
restic backup --quiet --tag studyaio --host studyaio-prod \
    --exclude "${SRC}/backups/*.partial" \
    "${SRC}/backups" "${SRC}/data"
# Cheap integrity check of repository metadata every run; a 1/50 data read weekly.
if [[ "$(date +%u)" == "7" ]]; then
    restic check --read-data-subset=1/50
else
    restic check
fi
end="$(date +%s)"

if [[ -d "$TEXTFILE_DIR" ]]; then
    tmp="$(mktemp "${TEXTFILE_DIR}/.studyaio_offsite.XXXXXX")"
    cat > "$tmp" <<PROM
# HELP studyaio_offsite_backup_last_success_timestamp_seconds Last successful off-host restic backup.
# TYPE studyaio_offsite_backup_last_success_timestamp_seconds gauge
studyaio_offsite_backup_last_success_timestamp_seconds ${end}
# HELP studyaio_offsite_backup_duration_seconds Duration of the last off-host backup.
# TYPE studyaio_offsite_backup_duration_seconds gauge
studyaio_offsite_backup_duration_seconds $((end - start))
PROM
    chmod 644 "$tmp"
    mv "$tmp" "${TEXTFILE_DIR}/studyaio_offsite.prom"
fi
echo "offsite: ok in $((end - start))s"

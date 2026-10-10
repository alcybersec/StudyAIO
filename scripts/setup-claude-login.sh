#!/usr/bin/env bash
# StudyAIO — create the dedicated Claude service-login directory (GL#8 / R-025).
#
# The worker gets its Claude CLI login from this directory and nothing else; it
# never sees the operator's personal ~/.claude. This script only creates the
# directory (0700, owned by the invoking user) and an empty settings.json so
# Docker does not auto-create a directory in its place. It copies NO existing
# credentials. Idempotent: safe to re-run.
#
# Usage: bash scripts/setup-claude-login.sh [DIR]
#   DIR defaults to $STUDYAIO_CLAUDE_LOGIN_DIR, then /opt/studyaio/claude-login.

set -euo pipefail

DIR="${1:-${STUDYAIO_CLAUDE_LOGIN_DIR:-/opt/studyaio/claude-login}}"

if [[ "$(id -u)" -eq 0 ]]; then
    echo "[ERROR] Run as the deploy user, not root, so the login is owned by it." >&2
    exit 1
fi

if [[ ! -d "$DIR" ]]; then
    if ! mkdir -p "$DIR" 2>/dev/null; then
        parent="$(dirname "$DIR")"
        echo "[ERROR] Cannot create $DIR. Create the parent once, e.g.:" >&2
        echo "        sudo install -d -o $(id -un) -g $(id -gn) -m 0755 $parent" >&2
        exit 1
    fi
fi
chmod 0700 "$DIR"

if [[ ! -e "$DIR/settings.json" ]]; then
    ( umask 077; echo '{}' > "$DIR/settings.json" )
fi

if [[ -s "$DIR/.credentials.json" ]]; then
    echo "[OK] $DIR exists and already holds a login. Re-run the login below only to rotate."
else
    echo "[OK] $DIR is ready; no login stored yet."
fi

cat <<MSG

One-time step, run by the operator on this host (opens the browser/device login):

    CLAUDE_CONFIG_DIR=$DIR claude login

Then set STUDYAIO_CLAUDE_LOGIN_DIR=$DIR in the deploy .env if it differs from
the default, and restart the worker:  docker compose up -d worker
MSG

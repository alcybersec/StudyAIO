#!/usr/bin/env bash
# StudyAIO — dedicated Claude service-login directory (GL#8 / R-025 / R-026).
#
# The worker gets its Claude login from this directory and nothing else; it
# never sees the operator's personal ~/.claude. The login is a long-lived token
# from `claude setup-token`, stored as <dir>/oauth-token (0600). This script:
#   1. creates the directory (0700, refuses root),
#   2. creates placeholder files so Docker does not create directories in place
#      of the single-file mounts (settings.json now, .credentials.json once the
#      token is saved),
#   3. reads the token from the terminal WITHOUT echo and writes it with
#      umask 077. It is never printed, never put in .env or shell history.
# It copies NO existing credentials. Idempotent; an existing token is kept
# unless you pass --rotate.
#
# Usage: bash scripts/setup-claude-login.sh [--rotate] [DIR]
#   DIR defaults to $STUDYAIO_CLAUDE_LOGIN_DIR, then /opt/studyaio/claude-login.
#   The token is read from the terminal, or from stdin when stdin is not a tty.

set -euo pipefail

ROTATE=0
ARGS=()
for a in "$@"; do
    case "$a" in
        --rotate) ROTATE=1 ;;
        *) ARGS+=("$a") ;;
    esac
done
DIR="${ARGS[0]:-${STUDYAIO_CLAUDE_LOGIN_DIR:-/opt/studyaio/claude-login}}"

if [[ "$(id -u)" -eq 0 ]]; then
    echo "[ERROR] Run as the deploy user, not root, so the login is owned by it." >&2
    exit 1
fi

if [[ "$(realpath -m "$DIR")" == "$(realpath -m "$HOME/.claude")" ]]; then
    echo "[ERROR] $DIR is your personal ~/.claude; the worker must use a dedicated directory." >&2
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

# Placeholders: without them Docker creates root-owned directories at these paths.
[[ -e "$DIR/settings.json" ]] || ( umask 077; echo '{}' > "$DIR/settings.json" )
# (.credentials.json is created only once a token is saved, below.)
placeholder() { [[ -e "$DIR/.credentials.json" ]] || ( umask 077; echo '{}' > "$DIR/.credentials.json" ); }

if [[ -s "$DIR/oauth-token" && "$ROTATE" -eq 0 ]]; then
    chmod 0600 "$DIR/oauth-token"
    placeholder
    echo "[OK] $DIR already holds a token. Re-run with --rotate to replace it."
    exit 0
fi

cat <<MSG
[OK] $DIR is ready.

Step 1. In another terminal, as this user, run:   claude setup-token
        (use a dedicated account/plan you can revoke) and copy the printed token.
Step 2. Paste it below. Input is hidden and the token is never echoed.
MSG

TOKEN=""
if [[ -t 0 ]]; then
    read -rs -p "Token: " TOKEN
    echo
else
    IFS= read -r TOKEN || true
fi
TOKEN="${TOKEN//[[:space:]]/}"
if [[ -z "$TOKEN" && ! -t 0 ]]; then
    echo "[OK] Directory prepared; no token supplied on stdin. Re-run interactively to save one"
    echo "     (do not run compose up until then: the .credentials.json mount source is missing)."
    exit 0
fi
if [[ -z "$TOKEN" ]]; then
    echo "[ERROR] No token entered; nothing written." >&2
    exit 1
fi

tmp="$(umask 077; mktemp "$DIR/.oauth-token.XXXXXX")"
printf '%s\n' "$TOKEN" > "$tmp"
chmod 0600 "$tmp"
mv -f "$tmp" "$DIR/oauth-token"
unset TOKEN
placeholder

echo "[OK] Token saved to $DIR/oauth-token (0600)."
echo "Set STUDYAIO_CLAUDE_LOGIN_DIR=$DIR in the deploy .env if it differs from the default,"
echo "then restart the worker:  docker compose up -d worker"

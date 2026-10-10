#!/usr/bin/env bash
# StudyAIO — Pre-flight configuration check
#
# Validates .env for common misconfigurations before deployment.
# Usage: bash scripts/preflight-check.sh [.env-file]

set -euo pipefail

ENV_FILE="${1:-.env}"

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

ERRORS=0
WARNINGS=0

error() { echo -e "${RED}[FAIL]${NC} $*"; ERRORS=$((ERRORS + 1)); }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; WARNINGS=$((WARNINGS + 1)); }
ok()    { echo -e "${GREEN}[ OK ]${NC} $*"; }

echo "StudyAIO Pre-flight Check"
echo "========================="
echo "Checking: $ENV_FILE"
echo ""

if [[ ! -f "$ENV_FILE" ]]; then
    error ".env file not found at $ENV_FILE"
    exit 1
fi

if [[ ! -r "$ENV_FILE" ]]; then
    error "$ENV_FILE exists but is not readable — run as its owner, or fix its mode."
    exit 1
fi

# Load .env (without exporting to avoid polluting shell)
# The trailing `|| true` on the reader pipeline matters: under `set -euo
# pipefail`, a key that is absent from the env file makes the reader exit
# non-zero, which (via pipefail) makes that pipeline return non-zero. Callers
# assign the result with `VAR=$(get_val ...)`, and that assignment failing
# trips `set -e` and kills the script right there — silently, with no error
# printed. `|| true` keeps a missing key behaving the same as get_val's own
# documented contract: empty string, not a crash. (The `local raw` declaration
# below is a separate statement from the assignment that follows it, so it does
# not swallow that assignment's exit status the way `local raw=$(...)` would.)
#
# Quoting mirrors python-dotenv's actual rules (config.py's env_file loader
# uses python-dotenv, and .env.example ships commented-out lines like
# `AGENT_BACKEND=claude_code   # claude_code | anthropic_api | ...` that an
# operator uncomments as-is, plus `secret-manager export --format=dotenv` — the
# secret-management pattern on hosts this script runs against — which
# single-quotes every value it emits):
#   - A single- or double-quoted value: the quotes delimit the value.
#     Anything after the closing quote (e.g. a trailing comment) is
#     discarded, but a `#` *inside* the quotes is literal value content, not
#     a comment marker — `POSTGRES_PASSWORD='ab#cd'` must not be truncated.
#   - A quoted value may span lines, and the newlines are part of the value:
#     python-dotenv reads to the *closing quote*, not to the end of the line.
#     A PEM private key and a pretty-printed JSON blob both arrive this way.
#     Reading one line of one would hand every check below a fragment — the
#     first `-----BEGIN ... KEY-----` and nothing else — which is not empty,
#     so an "is it set?" check passes and a comparison fails for a reason
#     nobody can see. Nothing in .env is multi-line today; the point is that
#     the day one is, this stops lying rather than starting to.
#   - An unquoted value ends at the newline (again matching python-dotenv), and
#     a whitespace-preceded `#...` inline comment is stripped along with
#     trailing whitespace. Without this, a value like
#     `GLOBAL_MAX_AI_CALLS_PER_DAY=0   # 0 = unlimited` would compare unequal
#     to both "0" and "", and the comment text would leak into every message.
#
# The awk below is the line-spanning reader: it takes everything after the
# first `KEY=`, and when that begins with a quote it keeps appending lines
# until the matching quote turns up. An unterminated quote prints what was
# accumulated rather than nothing — a malformed value should fail a comparison
# loudly, not disappear and read as "this key is not set".
get_val() {
    local raw
    raw=$(awk -v key="$1" '
        BEGIN { pat = "^" key "=" }
        !collecting && $0 ~ pat {
            raw = substr($0, length(key) + 2)
            rest = raw
            sub(/^[ \t]+/, "", rest)
            q = substr(rest, 1, 1)
            if (q == "\"" || q == "\047") {
                if (index(substr(rest, 2), q) > 0) { print raw; exit }
                collecting = 1
                acc = raw
                next
            }
            print raw
            exit
        }
        collecting {
            acc = acc "\n" $0
            if (index($0, q) > 0) { print acc; exit }
        }
        END { if (collecting) print acc }
    ' "$ENV_FILE" 2>/dev/null || true)
    if [[ "$raw" =~ ^[[:space:]]*\'(.*)\'[[:space:]]*(#.*)?$ ]]; then
        printf '%s' "${BASH_REMATCH[1]}"
    elif [[ "$raw" =~ ^[[:space:]]*\"(.*)\"[[:space:]]*(#.*)?$ ]]; then
        printf '%s' "${BASH_REMATCH[1]}"
    else
        printf '%s' "$raw" | sed -E 's/[[:space:]]+#.*$//; s/[[:space:]]+$//'
    fi
}

# ── JWT Secret ────────────────────────────────────────────────────

JWT_SECRET=$(get_val "JWT_SECRET_KEY")
SELF_HOSTED=$(get_val "SELF_HOSTED")
SINGLE_USER_MODE=$(get_val "SINGLE_USER_MODE")
BIND_HOST=$(get_val "BIND_HOST")
NO_AUTH_ACK=$(get_val "I_UNDERSTAND_NO_AUTH")

# The default key is committed to the repository, so anyone can sign a token with
# it. SELF_HOSTED=true no longer skips login (SEC-05), so with the default key an
# instance hands out forgeable admin tokens. Only SINGLE_USER_MODE (an anonymous
# caller already *is* the admin) gains nothing from a forged token.
if [[ "$JWT_SECRET" == "changeme-in-production-use-a-real-secret" ]]; then
    if [[ "$SINGLE_USER_MODE" == "true" ]]; then
        warn "JWT_SECRET_KEY is the committed default (tolerated only because SINGLE_USER_MODE=true)."
    else
        error "JWT_SECRET_KEY is the committed default — anyone can forge an admin token. Generate a new one:"
        echo "       python -c \"import secrets; print(secrets.token_urlsafe(64))\""
    fi
elif [[ -z "$JWT_SECRET" ]]; then
    error "JWT_SECRET_KEY is not set."
else
    ok "JWT_SECRET_KEY is set to a custom value"
fi

# ── Single-user ("no login") mode ─────────────────────────────────

if [[ "$SINGLE_USER_MODE" == "true" ]]; then
    case "$BIND_HOST" in
        127.0.0.1|localhost|::1)
            warn "SINGLE_USER_MODE=true — every caller is the admin. Safe only because BIND_HOST=$BIND_HOST is loopback; never put this behind a proxy."
            ;;
        *)
            if [[ "$NO_AUTH_ACK" == "true" ]]; then
                warn "SINGLE_USER_MODE=true with BIND_HOST='${BIND_HOST:-unset}' and I_UNDERSTAND_NO_AUTH=true — anyone who can reach this host is the admin."
            else
                warn "SINGLE_USER_MODE=true with BIND_HOST='${BIND_HOST:-unset}' (not loopback) — anyone who can reach this host is the admin, and startup will refuse it without I_UNDERSTAND_NO_AUTH=true."
            fi
            ;;
    esac
else
    # Without single-user mode the API will not start unless it can encrypt
    # per-user AI credentials at rest (SEC-06).
    if [[ -z "$(get_val SETTINGS_ENCRYPTION_KEY)" ]]; then
        warn "SETTINGS_ENCRYPTION_KEY is unset — the API will refuse to start without it (unless SINGLE_USER_MODE=true). Generate: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    else
        ok "SETTINGS_ENCRYPTION_KEY is set"
    fi
fi

# ── Database Password ─────────────────────────────────────────────

DB_PASS=$(get_val "POSTGRES_PASSWORD")

if [[ "$DB_PASS" == "studyaio" || -z "$DB_PASS" ]]; then
    warn "POSTGRES_PASSWORD is default ('studyaio'). Change it for production."
else
    ok "POSTGRES_PASSWORD is set to a custom value"
fi

# ── CORS Origins ──────────────────────────────────────────────────

CORS=$(get_val "CORS_ORIGINS")

if echo "$CORS" | grep -qE "localhost|127\.0\.0\.1"; then
    if [[ "$SELF_HOSTED" == "false" ]]; then
        warn "CORS_ORIGINS contains localhost — update for production domain."
    else
        ok "CORS_ORIGINS set (self-hosted mode, localhost acceptable)"
    fi
elif [[ -z "$CORS" ]]; then
    warn "CORS_ORIGINS is not set — API may reject browser requests."
else
    ok "CORS_ORIGINS: $CORS"
fi

# ── Registration gate ─────────────────────────────────────────────

REG_MODE=$(get_val "REGISTRATION_MODE")
REG_MODE=${REG_MODE:-open}

case "$REG_MODE" in
    invite)
        ok "REGISTRATION_MODE=invite — an invite code is required to sign up"
        ;;
    closed)
        ok "REGISTRATION_MODE=closed — nobody can create an account"
        ;;
    open)
        if [[ "$SELF_HOSTED" == "false" ]]; then
            warn "REGISTRATION_MODE=open — anyone who finds the URL can create an account. Use 'invite' for a closed beta."
        else
            ok "REGISTRATION_MODE=open (self-hosted mode)"
        fi
        ;;
    *)
        error "REGISTRATION_MODE='$REG_MODE' is not one of: open, invite, closed"
        ;;
esac

# ── Outbound email ────────────────────────────────────────────────

SMTP_HOST=$(get_val "SMTP_HOST")
SMTP_FROM=$(get_val "SMTP_FROM_EMAIL")

if [[ -z "$SMTP_HOST" || -z "$SMTP_FROM" ]]; then
    if [[ "$SELF_HOSTED" == "false" ]]; then
        error "SMTP_HOST/SMTP_FROM_EMAIL are unset — password resets and email verification will silently do nothing, locking out any user who forgets their password."
    else
        warn "SMTP is not configured — reset links are written to the API log instead of emailed."
    fi
else
    ok "SMTP configured ($SMTP_HOST)"
fi

# ── AI provider credentials ───────────────────────────────────────

# The worker's Claude login lives in a dedicated directory (R-025/R-026), never
# the personal ~/.claude. If it is missing at `compose up`, Docker creates
# root-owned directories in place of the single-file mounts.
check_claude_login_dir() {
    local dir="${STUDYAIO_CLAUDE_LOGIN_DIR:-$(get_val STUDYAIO_CLAUDE_LOGIN_DIR)}"
    dir="${dir:-/opt/studyaio/claude-login}"
    if [[ ! -d "$dir" ]]; then
        error "Claude login dir $dir is missing — run scripts/setup-claude-login.sh BEFORE compose up (Docker would create root-owned dirs in place of the file mounts)."
        return
    fi
    if [[ "$(realpath -m "$dir")" == "$(realpath -m "$HOME/.claude")" ]]; then
        error "Claude login dir resolves to \$HOME/.claude — the worker must use a dedicated directory, not your personal one."
        return
    fi
    local rdir rpersonal
    rdir="$(realpath -m "$dir")"; rpersonal="$(realpath -m "$HOME/.claude")"
    if [[ "$rpersonal" == "${rdir%/}/"* ]]; then
        error "Claude login dir $dir CONTAINS your personal ~/.claude (e.g. it is \$HOME) — use a dedicated directory."
        return
    fi
    local mode
    mode=$(stat -c '%a' "$dir")
    if (( (8#$mode & 8#007) != 0 )); then
        error "Claude login dir $dir is world-accessible (mode $mode) — chmod 700."
    else
        ok "Claude login dir $dir exists (mode $mode) and is dedicated"
    fi
    if [[ -s "$dir/oauth-token" ]]; then
        ok "Claude login: oauth-token present"
        local tmode
        tmode=$(stat -c '%a' "$dir/oauth-token")
        if [[ "$tmode" != "600" ]]; then
            error "Claude login: oauth-token is mode $tmode — chmod 600 $dir/oauth-token."
        fi
    elif [[ -s "$dir/.credentials.json" && "$(tr -d '[:space:]' < "$dir/.credentials.json")" != "{}" ]]; then
        warn "Claude login: only the .credentials.json fallback is present (it expires and is not refreshed) — run scripts/setup-claude-login.sh for a long-lived token."
    else
        error "Claude login dir $dir has no oauth-token — run scripts/setup-claude-login.sh."
    fi
    # settings.json is mounted over the CLI's own config: hooks, MCP servers or
    # permissions in it would hand the worker's CLI tools or commands.
    if [[ -f "$dir/settings.json" && "$(tr -d '[:space:]' < "$dir/settings.json")" == "{}" ]]; then
        ok "Claude login: settings.json is an empty {}"
    else
        error "Claude login: $dir/settings.json is missing or not exactly {} — hooks/MCP/permissions there give the worker's CLI tools or commands. Reset it to {}."
    fi
}

AGENT_BACKEND=$(get_val "AGENT_BACKEND")
AGENT_BACKEND=${AGENT_BACKEND:-claude_code}

# A backend selected without its key fails at the first pipeline stage, and the
# symptom (uploads that never produce a summary) points nowhere near the cause.
# Takes only the variable name — the backend label always comes from
# $AGENT_BACKEND, so there is no second copy of it to drift out of sync.
require_key() {
    local var="$1"
    if [[ -z "$(get_val "$var")" ]]; then
        error "AGENT_BACKEND=$AGENT_BACKEND but $var is unset — every pipeline run will fail."
    else
        ok "AGENT_BACKEND=$AGENT_BACKEND with $var set"
    fi
}

case "$AGENT_BACKEND" in
    zai)           require_key ZAI_API_KEY ;;
    openai)        require_key OPENAI_API_KEY ;;
    anthropic_api) require_key ANTHROPIC_API_KEY ;;
    claude_code)
        ok "AGENT_BACKEND=claude_code — login comes from the dedicated service-login dir"
        check_claude_login_dir
        ;;
    ollama)
        ok "AGENT_BACKEND=ollama — no API key required"
        ;;
    *)
        error "AGENT_BACKEND='$AGENT_BACKEND' is not one of: claude_code, anthropic_api, openai, zai, ollama"
        ;;
esac

# ── Spend ceiling ─────────────────────────────────────────────────

GLOBAL_CALLS=$(get_val "GLOBAL_MAX_AI_CALLS_PER_DAY")
GLOBAL_TOKENS=$(get_val "GLOBAL_MAX_AI_TOKENS_PER_DAY")
GLOBAL_CALLS=${GLOBAL_CALLS:-0}
GLOBAL_TOKENS=${GLOBAL_TOKENS:-0}

# Per-user quotas cannot bound the operator's bill: N testers times their
# individual limits is unbounded in aggregate. Only in SaaS mode — a
# self-hosted box is paying for its own usage.
if [[ "$SELF_HOSTED" == "false" ]]; then
    if [[ "$GLOBAL_CALLS" == "0" && "$GLOBAL_TOKENS" == "0" ]]; then
        warn "GLOBAL_MAX_AI_CALLS_PER_DAY and GLOBAL_MAX_AI_TOKENS_PER_DAY are both 0 (unlimited) — nothing caps what the instance spends."
    else
        ok "Spend ceiling set (calls=$GLOBAL_CALLS, tokens=$GLOBAL_TOKENS; 0 = unlimited)"
    fi
else
    ok "Spend ceiling not enforced (self-hosted — you are paying your own bill)"
fi

# ── Per-user limit vs the instance ceiling ────────────────────────

# A per-user daily limit only does useful work when it is small enough that one
# user cannot exhaust the instance ceiling on their own. Set them close together
# and the per-user number is decorative: the global ceiling always binds first,
# and it binds first-come-first-served — whoever uploads earliest that day
# spends everybody else's budget. See issue #35.

FREE_CALLS=$(get_val "FREE_MAX_AI_CALLS_PER_DAY")
FREE_CALLS=${FREE_CALLS:-0}

# Only meaningful when both are enforced: 0 means unlimited on either side, and
# self-hosted skips per-user quotas entirely.
if [[ "$SELF_HOSTED" == "false" && "$GLOBAL_CALLS" != "0" && "$FREE_CALLS" != "0" ]]; then
    if [[ "$FREE_CALLS" =~ ^[0-9]+$ && "$GLOBAL_CALLS" =~ ^[0-9]+$ ]]; then
        CONCURRENT=$((GLOBAL_CALLS / FREE_CALLS))
        if [[ "$CONCURRENT" -lt 3 ]]; then
            warn "FREE_MAX_AI_CALLS_PER_DAY=$FREE_CALLS against GLOBAL_MAX_AI_CALLS_PER_DAY=$GLOBAL_CALLS — only $CONCURRENT user(s) can reach their own limit before the instance ceiling is exhausted, so one user can lock out the rest. Aim for roughly ceiling / expected concurrent users."
        else
            ok "Per-user limit leaves room for ~$CONCURRENT users within the instance ceiling"
        fi
    fi
fi

# ── Per-user provider overrides ───────────────────────────────────

# AGENT_BACKEND above is only the *default*. A user who picked their own
# provider in Settings runs on that instead, and this script reads .env — it
# cannot see the database. Reporting the env backend as correct while a user
# runs something else is exactly the blindness issue #26 describes, so look if
# we can and say so plainly if we cannot.

DB_CONTAINER="${PREFLIGHT_DB_CONTAINER:-studyaio-db-1}"

if ! command -v docker >/dev/null 2>&1; then
    ok "Per-user provider overrides not checked (docker not available here)"
elif ! docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$DB_CONTAINER"; then
    ok "Per-user provider overrides not checked ($DB_CONTAINER is not running)"
else
    OVERRIDES=$(docker exec "$DB_CONTAINER" psql -U "${POSTGRES_USER:-studyaio}" -d "${POSTGRES_DB:-studyaio}" -tAc \
        "select count(*) from user_settings where settings_json ? 'agent_backend' and settings_json->>'agent_backend' <> 'studyaio'" 2>/dev/null || echo "")

    if [[ -z "$OVERRIDES" ]]; then
        ok "Per-user provider overrides not checked (could not query $DB_CONTAINER)"
    elif [[ "$OVERRIDES" == "0" ]]; then
        ok "No per-user provider overrides — every account uses AGENT_BACKEND=$AGENT_BACKEND"
    else
        warn "$OVERRIDES account(s) run their own AI provider, not AGENT_BACKEND=$AGENT_BACKEND. That is a supported feature, but it means this check does not describe what those pipelines actually use. Inspect with: SELECT user_id, settings_json->>'agent_backend' FROM user_settings WHERE settings_json->>'agent_backend' <> 'studyaio';"
    fi
fi

# ── Cookie Secure ─────────────────────────────────────────────────

COOKIE_SECURE=$(get_val "COOKIE_SECURE")

if [[ "$COOKIE_SECURE" == "false" || -z "$COOKIE_SECURE" ]]; then
    warn "COOKIE_SECURE is false — set to true when using HTTPS."
else
    ok "COOKIE_SECURE is enabled"
fi

# ── OpenAPI ───────────────────────────────────────────────────────

OPENAPI=$(get_val "OPENAPI_ENABLED")

if [[ "$OPENAPI" == "true" || -z "$OPENAPI" ]]; then
    warn "OPENAPI_ENABLED is true (or unset) — /docs is exposed. Set to false in production."
else
    ok "OpenAPI docs are disabled"
fi

# ── Data Directory ────────────────────────────────────────────────

DATA_DIR=$(get_val "DATA_DIR")
DATA_DIR="${DATA_DIR:-/app/data}"

if [[ -d "$DATA_DIR" ]]; then
    ok "Data directory exists: $DATA_DIR"
elif [[ -d "./data" ]]; then
    ok "Data directory exists: ./data"
else
    warn "Data directory not found locally (may be fine inside Docker)"
fi

# ── Summary ───────────────────────────────────────────────────────

echo ""
echo "========================="
if [[ $ERRORS -gt 0 ]]; then
    echo -e "${RED}$ERRORS error(s)${NC}, ${YELLOW}$WARNINGS warning(s)${NC}"
    echo "Fix errors before deploying."
    exit 1
elif [[ $WARNINGS -gt 0 ]]; then
    echo -e "${GREEN}0 errors${NC}, ${YELLOW}$WARNINGS warning(s)${NC}"
    echo "Review warnings before deploying."
    exit 0
else
    echo -e "${GREEN}All checks passed!${NC}"
    exit 0
fi

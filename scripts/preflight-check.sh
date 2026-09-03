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

# Load .env (without exporting to avoid polluting shell)
# The trailing `|| true` matters: under `set -euo pipefail`, a key that is
# absent from the env file makes grep exit 1, which (via pipefail) makes this
# whole function return 1. Callers assign the result with `VAR=$(get_val ...)`,
# and that assignment failing trips `set -e` and kills the script right there
# — silently, with no error printed. `|| true` keeps a missing key behaving
# the same as get_val's own documented contract: empty string, not a crash.
get_val() {
    grep -E "^${1}=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- | sed 's/^"//' | sed 's/"$//' || true
}

# ── JWT Secret ────────────────────────────────────────────────────

JWT_SECRET=$(get_val "JWT_SECRET_KEY")
SELF_HOSTED=$(get_val "SELF_HOSTED")

if [[ "$JWT_SECRET" == "changeme-in-production-use-a-real-secret" ]]; then
    if [[ "$SELF_HOSTED" == "false" ]]; then
        error "JWT_SECRET_KEY is set to default value (SaaS mode). Generate a new one:"
        echo "       python -c \"import secrets; print(secrets.token_urlsafe(64))\""
    else
        warn "JWT_SECRET_KEY is set to default value. Consider changing it for security."
    fi
elif [[ -z "$JWT_SECRET" ]]; then
    error "JWT_SECRET_KEY is not set."
else
    ok "JWT_SECRET_KEY is set to a custom value"
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

AGENT_BACKEND=$(get_val "AGENT_BACKEND")
AGENT_BACKEND=${AGENT_BACKEND:-claude_code}

# A backend selected without its key fails at the first pipeline stage, and the
# symptom (uploads that never produce a summary) points nowhere near the cause.
require_key() {
    local backend="$1" var="$2"
    if [[ -z "$(get_val "$var")" ]]; then
        error "AGENT_BACKEND=$backend but $var is unset — every pipeline run will fail."
    else
        ok "AGENT_BACKEND=$backend with $var set"
    fi
}

case "$AGENT_BACKEND" in
    zai)           require_key zai ZAI_API_KEY ;;
    openai)        require_key openai OPENAI_API_KEY ;;
    anthropic_api) require_key anthropic_api ANTHROPIC_API_KEY ;;
    claude_code)
        ok "AGENT_BACKEND=claude_code — credentials come from the mounted ~/.claude"
        ;;
    ollama)
        ok "AGENT_BACKEND=ollama — no API key required"
        ;;
    *)
        error "AGENT_BACKEND='$AGENT_BACKEND' is not one of: claude_code, anthropic_api, openai, zai, ollama"
        ;;
esac

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

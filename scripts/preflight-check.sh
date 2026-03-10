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
get_val() {
    grep -E "^${1}=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- | sed 's/^"//' | sed 's/"$//'
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

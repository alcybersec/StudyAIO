#!/usr/bin/env bash
# Files migrated to the token system must not reintroduce raw palette classes.
# The allowlist shrinks as D-streams migrate files; Stream F deletes it entirely.
set -u

# Run from the repo root regardless of invocation cwd (npm run lint runs in services/ui).
cd "$(dirname "$0")/../../.."

PATTERN='(bg|text|border)-(gray|slate|zinc|red|green|blue|amber|orange|pink|purple|indigo|emerald|teal)-[0-9]'
ALLOWLIST='services/ui/scripts/color-allowlist.txt'   # shrinks as D-streams migrate files
violations=$(grep -rnE "$PATTERN" services/ui/src --include='*.tsx' --include='*.ts' | grep -vFf "$ALLOWLIST" || true)
if [ -n "$violations" ]; then echo "$violations"; echo 'Raw palette classes found — use tokens.'; exit 1; fi

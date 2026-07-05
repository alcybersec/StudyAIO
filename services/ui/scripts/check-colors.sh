#!/usr/bin/env bash
# The UI is fully migrated to the token system — raw palette classes are forbidden.
set -u

# Run from the repo root regardless of invocation cwd (npm run lint runs in services/ui).
cd "$(dirname "$0")/../../.."

PATTERN='(bg|text|border)-(gray|slate|zinc|red|green|blue|amber|orange|pink|purple|indigo|emerald|teal)-[0-9]'
violations=$(grep -rnE "$PATTERN" services/ui/src --include='*.tsx' --include='*.ts' || true)
if [ -n "$violations" ]; then echo "$violations"; echo 'Raw palette classes found — use tokens.'; exit 1; fi

#!/usr/bin/env bash
# The UI is fully migrated to the token system.
#  1. Raw Tailwind palette classes are forbidden (use tokens).
#  2. Legacy compatibility-shim tokens are forbidden (they map to the wrong
#     Nordic Calm colors — e.g. `-primary` renders periwinkle where sage is
#     meant). Use the new tokens directly: sage / amber / red / peri (+ -soft
#     / -fg / -hover), surface-0/1/2, border, text / text-muted / text-faint,
#     on-accent.
set -u

# Run from the repo root regardless of invocation cwd (npm run lint runs in services/ui).
cd "$(dirname "$0")/../../.."

status=0

# 1. Raw palette classes (bg-red-500, text-gray-200, …)
RAW_PATTERN='(bg|text|border)-(gray|slate|zinc|red|green|blue|amber|orange|pink|purple|indigo|emerald|teal)-[0-9]'
raw=$(grep -rnE "$RAW_PATTERN" services/ui/src --include='*.tsx' --include='*.ts' || true)
if [ -n "$raw" ]; then echo "$raw"; echo 'Raw palette classes found — use tokens.'; status=1; fi

# 2. Legacy compatibility-shim tokens.
#    - (bg|text|border|ring)-primary (+ -dark / -light / /opacity)
#    - bare bg-surface / text-surface and bg-surface-alt / -hover
#      (surface-0/1/2 and surface-strong stay — the (?![-\w]) lookahead skips them)
#    - text-white on colored backgrounds (use on-accent)
#    - (bg|text|border)-(danger|success|warning)  → red / sage / amber
LEGACY_PATTERN='(bg|text|border|ring)-primary(-dark|-light)?|(bg|text|border)-(danger|success|warning)|text-white|(bg|text)-surface(-alt|-hover)?(?![-\w])'
legacy=$(grep -rnP "$LEGACY_PATTERN" services/ui/src --include='*.tsx' --include='*.ts' || true)
if [ -n "$legacy" ]; then echo "$legacy"; echo 'Legacy shim tokens found — migrate to the Nordic Calm tokens (sage/amber/red/peri, surface-0/1/2, on-accent).'; status=1; fi

exit $status

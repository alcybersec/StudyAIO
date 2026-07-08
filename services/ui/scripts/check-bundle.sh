#!/usr/bin/env bash
# Bundle size budget: no file in dist/assets may exceed 500KB.
# Run after `npm run build`.
#
# Exception: pdf.worker.min-*.mjs is the pre-minified pdfjs-dist worker binary
# (~1MB upstream, not code-splittable, lazily fetched only when the PDF viewer
# opens a document). It is excluded from the budget.
set -u

cd "$(dirname "$0")/.."

if [ ! -d dist/assets ]; then
  echo 'dist/assets not found — run `npm run build` first.' >&2
  exit 1
fi

oversized=$(find dist/assets -type f -size +500k ! -name 'pdf.worker.min-*.mjs')
if [ -n "$oversized" ]; then
  echo 'Bundle budget exceeded (>500KB):' >&2
  # shellcheck disable=SC2086
  du -k $oversized | sort -rn >&2
  exit 1
fi

echo 'Bundle budget OK (all dist/assets files <= 500KB).'

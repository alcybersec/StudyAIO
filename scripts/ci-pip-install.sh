#!/usr/bin/env bash
# Install the backend's runtime AND test dependencies (requirements-dev.txt) from services/app/requirements.lock.txt
# WITHOUT running pip's resolver. Used by every CI job that needs the backend
# (backend-tests, test-floor, integration-tests, e2e-tests) so they install
# identically.
#
# Why (GL#7): e2e-tests failed with ResolutionImpossible on an unchanged
# requirements.txt. pip backtracked through every aiogram release
# because aiohttp had NO candidates -- it was never fetched -- i.e. an index
# lookup came back empty/slow (the trace shows multi-minute stalls) and the
# resolver reported that as a version conflict. A constraints file does not help:
# the resolver still has to ask the index for every candidate. Here there is
# nothing to resolve: each lock line is fetched by exact name==version, so an
# index fault surfaces as "No matching distribution found for <pkg>==<ver>"
# naming the culprit, not as a 40-release backtrack.
#
# Each package comes from exactly ONE index: local-version pins (torch==x+cpu)
# from the PyTorch CPU index, everything else from PyPI. No --extra-index-url, so
# one index's hiccup cannot change what the other resolves.
#
# Afterwards: --no-index re-check of requirements-dev.txt (which includes requirements.txt) (fails if someone edited it
# without re-running scripts/lock-requirements.sh) and `pip check`.
#
# Run it with the interpreter you want populated (the venv's on PATH, or the
# image's python). Nothing here touches the network except the two installs.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REQ="$REPO_ROOT/services/app/requirements-dev.txt"
LOCK="$REPO_ROOT/services/app/requirements.lock.txt"
PYPI="https://pypi.org/simple"
TORCH_CPU="https://download.pytorch.org/whl/cpu"
PY="${PYTHON:-python}"

# Ambient index/constraint settings would re-introduce the second index or a
# resolver pass; this script owns both.
unset PIP_EXTRA_INDEX_URL PIP_INDEX_URL PIP_CONSTRAINT PIP_REQUIRE_VIRTUALENV

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

grep -E '^[A-Za-z0-9]' "$LOCK" | grep    '+' > "$WORK/local.txt" || true
grep -E '^[A-Za-z0-9]' "$LOCK" | grep -v '+' > "$WORK/pypi.txt"

echo "lock: $(wc -l < "$WORK/pypi.txt") PyPI pins, $(wc -l < "$WORK/local.txt") local-version pins"

if [ -s "$WORK/local.txt" ]; then
  "$PY" -m pip install --no-deps --index-url "$TORCH_CPU" -r "$WORK/local.txt"
fi
"$PY" -m pip install --no-deps --index-url "$PYPI" -r "$WORK/pypi.txt"

# Offline: every top-level requirement must already be satisfied by the lock.
"$PY" -m pip install --no-index --no-deps -r "$REQ"
"$PY" -m pip check

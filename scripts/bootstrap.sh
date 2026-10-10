#!/usr/bin/env bash
#
# Build services/app/.venv from requirements.txt, constrained by the lock file.
#
# Mirrors the CI backend-tests install (.gitlab-ci.yml): PIP_CONSTRAINT points at
# requirements.lock.txt and the CPU-only torch index is added, so a clean clone
# resolves the same versions CI tested and does not pull the multi-GB CUDA wheels.
#
# Needs Python 3.12 (python3.12 on PATH) or uv, which fetches one on demand.
# Idempotent: `make test` re-runs it only when requirements change (stamp file).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$REPO_ROOT/services/app"
VENV="$APP_DIR/.venv"

if [ ! -x "$VENV/bin/python" ]; then
  if command -v python3.12 >/dev/null 2>&1; then
    python3.12 -m venv "$VENV"
  elif command -v uv >/dev/null 2>&1; then
    uv venv --seed --python 3.12 "$VENV"
  else
    echo "FATAL: need python3.12 or uv on PATH to create $VENV" >&2
    exit 1
  fi
fi

export PIP_CONSTRAINT="$APP_DIR/requirements.lock.txt"
export PIP_EXTRA_INDEX_URL="${PIP_EXTRA_INDEX_URL:-https://download.pytorch.org/whl/cpu}"

"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install -r "$APP_DIR/requirements.txt"
touch "$VENV/.bootstrap-stamp"
echo "bootstrap: $VENV ready ($("$VENV/bin/python" --version))"

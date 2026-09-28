#!/usr/bin/env bash
# Regenerate services/app/requirements.lock.txt from requirements.txt.
#
# The lock is a CONSTRAINTS file, not an install list. requirements.txt still
# decides *what* is installed; the lock only pins the version of everything that
# gets pulled in, direct and transitive. CI passes it via PIP_CONSTRAINT, and
# services/app/Dockerfile passes it with -c, so the image ships the versions CI
# tested.
#
# Why this exists: GL#7. e2e-tests failed with ResolutionImpossible on an
# unchanged requirements.txt and passed on a plain retry. Whatever the trigger,
# a resolve that consults the network for candidate versions on every run can
# fail on a run where nothing changed. Pinned versions remove that exposure.
#
# Run it in the SAME image and index configuration CI uses, or the pins will not
# be the ones CI can install:
#   - python:3.12-slim   — the base in .gitlab-ci.yml and services/app/Dockerfile
#   - PIP_EXTRA_INDEX_URL — the torch CPU index, set globally in .gitlab-ci.yml
#
# Regenerate whenever you change requirements.txt. If you forget, the install
# does not silently drift — it fails when a new dependency conflicts with a pin,
# which is the signal to re-run this.
#
# Usage:  ./scripts/lock-requirements.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REQ="$REPO_ROOT/services/app/requirements.txt"
LOCK="$REPO_ROOT/services/app/requirements.lock.txt"

# Must match `variables:` in .gitlab-ci.yml.
PYTHON_IMAGE="python:3.12-slim"
EXTRA_INDEX="https://download.pytorch.org/whl/cpu"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
chmod 777 "$WORK"

echo "Resolving $REQ in $PYTHON_IMAGE ..."
docker run --rm \
  -e PIP_EXTRA_INDEX_URL="$EXTRA_INDEX" \
  -e PIP_DISABLE_PIP_VERSION_CHECK=1 \
  -v "$REQ:/r.txt:ro" \
  -v "$WORK:/out" \
  "$PYTHON_IMAGE" \
  sh -c "pip install -q --dry-run --report /out/report.json -r /r.txt"

python3 - "$WORK/report.json" "$LOCK" "$EXTRA_INDEX" <<'PY'
import json
import sys
from datetime import UTC, datetime

report_path, lock_path, extra_index = sys.argv[1:4]

with open(report_path) as fh:
    report = json.load(fh)

# metadata.name is the canonical name pip resolved; version comes from the same
# metadata block, so this records exactly what pip decided to install.
pins = sorted(
    (item["metadata"]["name"].lower(), item["metadata"]["version"])
    for item in report["install"]
)

header = f"""\
# GENERATED FILE — do not edit by hand.
# Regenerate with ./scripts/lock-requirements.sh
#
# Constraints for every pip install in this repo: CI via PIP_CONSTRAINT in
# .gitlab-ci.yml, and the image via -c in services/app/Dockerfile. This pins the
# version of every package the resolver reaches, direct and transitive, so an
# install does not depend on what the index offers on the day, and so the image
# ships the versions CI tested. See GL#7.
#
# requirements.txt remains the source of truth for WHAT is installed. Adding a
# dependency there does not require regenerating this immediately — but if the
# new dependency conflicts with a pin below, the install fails, and that is the
# cue to re-run the script.
#
# Resolved {datetime.now(UTC).strftime('%Y-%m-%d')} on python:3.12-slim,
# linux/amd64, with extra index {extra_index}.
# {len(pins)} packages.
"""

with open(lock_path, "w") as fh:
    fh.write(header)
    for name, version in pins:
        fh.write(f"{name}=={version}\n")

print(f"Wrote {lock_path} — {len(pins)} pins")
PY

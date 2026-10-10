#!/usr/bin/env bash
# Dependency vulnerability audit (SEC-07 / GL#27).
#
#   scripts/audit-deps.sh            # both ecosystems
#   scripts/audit-deps.sh pip        # services/app/requirements.lock.txt only
#   scripts/audit-deps.sh npm        # services/ui/package-lock.json only
#
# pip: pip-audit over the pinned lock. npm: `npm audit --audit-level=high`.
# Exceptions live in infra/audit-allowlist.txt (`pip:<id>` / `npm:<GHSA id>`), each
# with a justification. Requires pip-audit on PATH (pip install pip-audit) and,
# for npm, node_modules-free `npm audit` (it reads the lock only).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ALLOWLIST="$REPO_ROOT/infra/audit-allowlist.txt"
TARGET="${1:-all}"
rc=0

allowed() { # allowed <pip|npm> -> one id per line
  grep -E "^$1:" "$ALLOWLIST" 2>/dev/null | sed -E "s/^$1:([^[:space:]#]+).*/\1/" || true
}

audit_pip() {
  local work lock ignores=()
  work="$(mktemp -d)"
  trap 'rm -rf "$work"' RETURN
  # pip-audit cannot look up local-version pins such as torch==2.14.1+cpu on PyPI.
  sed -E 's/\+cpu$//' "$REPO_ROOT/services/app/requirements.lock.txt" | grep -E '^[A-Za-z0-9_.-]+==' > "$work/lock.txt"
  while read -r id; do [ -n "$id" ] && ignores+=(--ignore-vuln "$id"); done < <(allowed pip)
  echo "==> pip-audit (services/app/requirements.lock.txt)"
  pip-audit -r "$work/lock.txt" --no-deps --disable-pip --strict "${ignores[@]}" || rc=1
}

audit_npm() {
  local work
  work="$(mktemp -d)"
  trap 'rm -rf "$work"' RETURN
  echo "==> npm audit --audit-level=high (services/ui)"
  allowed npm > "$work/allow.txt"
  (cd "$REPO_ROOT/services/ui" && npm audit --json > "$work/audit.json") || true
  python3 - "$work/audit.json" "$work/allow.txt" <<'PY' || rc=1
import json
import sys

audit = json.load(open(sys.argv[1]))
allow = {line.strip() for line in open(sys.argv[2]) if line.strip()}
if "vulnerabilities" not in audit:
    sys.exit(f"npm audit failed: {audit.get('error') or audit}")
bad = []
for name, vuln in audit["vulnerabilities"].items():
    for via in vuln["via"]:
        if not isinstance(via, dict) or via.get("severity") not in ("high", "critical"):
            continue
        ghsa = via["url"].rsplit("/", 1)[-1]
        if ghsa not in allow:
            bad.append(f"{name}: {via['severity']} {ghsa} {via['title']}")
for line in sorted(set(bad)):
    print(line)
print(f"{len(set(bad))} unallowlisted high/critical npm advisories")
sys.exit(1 if bad else 0)
PY
}

case "$TARGET" in
  pip) audit_pip ;;
  npm) audit_npm ;;
  all) audit_pip; audit_npm ;;
  *) echo "usage: $0 [pip|npm|all]" >&2; exit 2 ;;
esac
exit "$rc"

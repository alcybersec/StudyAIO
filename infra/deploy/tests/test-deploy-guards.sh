#!/usr/bin/env bash
# Hermetic test for the deployability guards in infra/deploy/deploy.sh
# (enforce_main_only): ancestor-of-main -> exit 65, stale host script -> exit 71,
# current OR previous main copy of the script accepted.
#
# Builds a throwaway origin + deploy checkout in a temp dir; touches nothing else.
#   bash infra/deploy/tests/test-deploy-guards.sh
# DEPLOY_SH=<path> runs the same cases against another copy of the script (used
# for revert checks: a deliberately broken copy must make this test fail).
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_SH="${DEPLOY_SH:-${HERE}/../deploy.sh}"
[ -f "$DEPLOY_SH" ] || { echo "no script at ${DEPLOY_SH}" >&2; exit 2; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@example.invalid
export GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@example.invalid

# Load only the function definitions (deploy.sh returns early when sourced).
# shellcheck source=/dev/null
source "$DEPLOY_SH"
set +e   # the sourced script turned errexit on; cases below inspect exit codes

ORIGIN="${TMP}/origin.git"
WORK="${TMP}/work"
DEPLOY="${TMP}/deploy"
git init -q --bare -b main "$ORIGIN"
git clone -q "$ORIGIN" "$WORK" 2>/dev/null
cd "$WORK" || exit 2
git checkout -q -b main
mkdir -p infra/deploy

commit_script() { # version-label -> commit sha on stdout
    printf '#!/usr/bin/env bash\n# version %s\n' "$1" > infra/deploy/deploy.sh
    git add infra/deploy/deploy.sh
    git commit -q -m "script $1"
    git rev-parse HEAD
}
commit_other() {
    echo "$1" > "other-$1.txt"
    git add "other-$1.txt"
    git commit -q -m "other $1"
    git rev-parse HEAD
}

commit_script v1 >/dev/null
OLD_MAIN="$(commit_other a)"
commit_script v2 >/dev/null
MAIN_TIP="$(commit_other b)"
git push -q origin main 2>/dev/null
git checkout -q -b feature
BRANCH_SHA="$(commit_other branch-only)"
git push -q origin feature 2>/dev/null

# The deploy checkout fetches EVERYTHING here on purpose: the branch commit is
# present locally, so only the ancestor check can keep it out.
git clone -q "$ORIGIN" "$DEPLOY" 2>/dev/null
cd "$DEPLOY" || exit 2
git fetch -q origin "+refs/heads/main:refs/remotes/origin/main"
git fetch -q origin "+refs/heads/feature:refs/remotes/origin/feature"

host_copy() { # label -> path of a host script holding the bytes of that version
    local f="${TMP}/host-$1.sh"
    printf '#!/usr/bin/env bash\n# version %s\n' "$1" > "$f"
    echo "$f"
}
HOST_V1="$(host_copy v1)"
HOST_V2="$(host_copy v2)"
HOST_TAMPERED="${TMP}/host-tampered.sh"
printf '#!/usr/bin/env bash\n# version v2\necho pwned\n' > "$HOST_TAMPERED"
HOST_ANCIENT="$(host_copy v0)"

FAIL=0
run_case() { # name expected-rc self sha
    local name="$1" want="$2" self="$3" sha="$4" got out
    out="$( (enforce_main_only "$self" "$sha") 2>&1 )"
    got=$?
    if [ "$got" -eq "$want" ]; then
        printf 'ok   %s (exit %s)\n' "$name" "$got"
    else
        printf 'FAIL %s: want exit %s, got %s\n%s\n' "$name" "$want" "$got" "$out"
        FAIL=1
    fi
}

# Host copy == main's current script.
run_case "main tip, host=current            -> proceeds" 0 "$HOST_V2" "$MAIN_TIP"
run_case "older main commit, host=current   -> proceeds (re-deploy)" 0 "$HOST_V2" "$OLD_MAIN"
run_case "abbreviated main sha              -> proceeds" 0 "$HOST_V2" "${MAIN_TIP:0:7}"
# Host copy == the PREVIOUS main version (the deploy of the commit that changes it).
run_case "main tip, host=previous version   -> proceeds" 0 "$HOST_V1" "$MAIN_TIP"
# Stale / tampered host copy.
run_case "host older than previous          -> 71" 71 "$HOST_ANCIENT" "$MAIN_TIP"
run_case "host tampered                     -> 71" 71 "$HOST_TAMPERED" "$MAIN_TIP"
# Branch-only commit with an otherwise valid host copy.
run_case "branch-only sha, host=current     -> 65" 65 "$HOST_V2" "$BRANCH_SHA"
run_case "branch-only sha, host=previous    -> 65" 65 "$HOST_V1" "$BRANCH_SHA"
run_case "unknown sha                       -> 65" 65 "$HOST_V2" "0123456789abcdef0123456789abcdef01234567"
# The drift guard runs first: a bad script is refused even for a main SHA.
run_case "branch-only sha, host tampered    -> 71" 71 "$HOST_TAMPERED" "$BRANCH_SHA"

# A third version on main: v1 is no longer "previous", v2 is.
cd "$WORK" || exit 2
git checkout -q main
V3_COMMIT="$(commit_script v3)"
git push -q origin main 2>/dev/null
cd "$DEPLOY" || exit 2
git fetch -q origin "+refs/heads/main:refs/remotes/origin/main"
HOST_V3="$(host_copy v3)"
run_case "after v3: host=current v3         -> proceeds" 0 "$HOST_V3" "$V3_COMMIT"
run_case "after v3: host=previous v2        -> proceeds" 0 "$HOST_V2" "$V3_COMMIT"
run_case "after v3: host=two versions back  -> 71" 71 "$HOST_V1" "$V3_COMMIT"

# A revert to an earlier blob must not make "previous" equal "current".
cd "$WORK" || exit 2
commit_script v3 >/dev/null   # identical bytes again: empty commit is not created
git commit -q --allow-empty -m "noop"
git push -q origin main 2>/dev/null
cd "$DEPLOY" || exit 2
git fetch -q origin "+refs/heads/main:refs/remotes/origin/main"
run_case "unchanged-script commit: previous still v2" 0 "$HOST_V2" "$(git rev-parse refs/remotes/origin/main)"

[ "$FAIL" -eq 0 ] && echo "all deploy guard cases passed" || echo "deploy guard cases FAILED"
exit "$FAIL"

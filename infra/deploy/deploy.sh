#!/usr/bin/env bash
# Forced command for the CI deploy key (authorized_keys).
# Rewritten 2026-09-27 when CI moved to GitLab.
#
# CANONICAL COPY: infra/deploy/deploy.sh in the StudyAIO repo. The live file is
# /opt/studyaio/deploy.sh on the deploy host and is deliberately UNTRACKED there
# -- `git checkout --force` during a deploy must not rewrite the script that is
# currently executing, because bash reads a script incrementally and would run
# the tail of the new file against the state of the old one. So this is applied
# by hand; see docs/deployment.md. Keep the two in step.
#
# The CI job supplies ONE argument -- the commit SHA that passed CI -- via
# SSH_ORIGINAL_COMMAND. Everything else happens here, which is what lets the key
# stay command-restricted: the deploy needs no scp and no arbitrary ssh, so a
# leaked key still cannot run anything but this script.
#
# Deliberately pulls images rather than building locally. The previous version
# ran `compose build`, and because the base compose declares build: for
# ui/api/worker/beat while the prod overlay sets image: ghcr.io/..., that built
# LOCAL images tagged with the GHCR names -- shadowing the very artifacts CI had
# tested. Pulling the exact tag keeps "what was tested" and "what runs" identical.
set -euo pipefail

# --- Image retention ----------------------------------------------------------
# Defined BEFORE the work starts so a test can `source` this file for the
# functions alone (see the guard below the definitions).
#
# select_stale_app_refs KEEP CURRENT_TAG OWNER < listing
#   listing: one image per line, TAB-separated: repository, tag, created
#            (docker images --format '{{.Repository}}\t{{.Tag}}\t{{.CreatedAt}}')
#   prints:  repository:tag of every APP image (ghcr.io/OWNER/studyaio-api and
#            studyaio-ui) whose tag is not among the KEEP most recent releases,
#            CURRENT_TAG always being one of them. A "release" is a tag; recency
#            is the newest creation time of any app image carrying it. Images
#            of other repositories (db, redis, ...) are never listed.
select_stale_app_refs() {
    local keep="$1" current="$2" owner="$3"
    awk -F'\t' -v keep="$keep" -v cur="$current" -v owner="$owner" '
        BEGIN { api = "ghcr.io/" owner "/studyaio-api"; ui = "ghcr.io/" owner "/studyaio-ui" }
        ($1 == api || $1 == ui) {
            n++; refs[n] = $1 ":" $2; tags[n] = $2
            if ($2 != "<none>" && $3 > newest[$2]) newest[$2] = $3
        }
        END {
            # Rank tags newest-first (selection sort; a handful of tags at most).
            for (t in newest) if (t != cur) order[++m] = t
            for (i = 1; i <= m; i++)
                for (j = i + 1; j <= m; j++)
                    if (newest[order[j]] > newest[order[i]]) { x = order[i]; order[i] = order[j]; order[j] = x }
            kept[cur] = 1
            for (i = 1; i <= keep - 1 && i <= m; i++) kept[order[i]] = 1
            for (i = 1; i <= n; i++) if (!(tags[i] in kept) && tags[i] != "<none>") print refs[i]
        }
    '
}

# prune_old_app_images KEEP CURRENT_TAG OWNER
# Untags stale app images, then drops what became dangling. Never removes an
# image a container (running or stopped) references, and never touches a
# non-app image.
prune_old_app_images() {
    local keep="$1" current="$2" owner="$3" in_use ref
    in_use="$(docker ps -a --format '{{.Image}}' 2>/dev/null || true)"
    while read -r ref; do
        [ -n "$ref" ] || continue
        if grep -qxF -- "$ref" <<< "$in_use"; then
            echo "    keeping ${ref} (used by a container)"
            continue
        fi
        echo "    removing ${ref}"
        docker rmi "$ref" >/dev/null 2>&1 || echo "    (could not remove ${ref}; left in place)"
    done < <(docker images --format '{{.Repository}}\t{{.Tag}}\t{{.CreatedAt}}' \
                | select_stale_app_refs "$keep" "$current" "$owner")
    docker image prune -f >/dev/null 2>&1 || true
}

# Sourced (by a test): stop after the definitions instead of deploying.
[[ "${BASH_SOURCE[0]}" == "$0" ]] || return 0


KEEP_RELEASES="${KEEP_RELEASES:-2}"
if ! [[ "$KEEP_RELEASES" =~ ^[1-9][0-9]*$ ]]; then
    echo "refusing: KEEP_RELEASES must be a positive integer, got '${KEEP_RELEASES}'" >&2
    exit 64
fi

cd /opt/studyaio

# Validate strictly. The forced command means this is the only entry point, so
# this pattern is the whole input surface -- anything not a hex SHA is refused.
REQ="${SSH_ORIGINAL_COMMAND:-}"
if ! [[ "$REQ" =~ ^[0-9a-f]{7,40}$ ]]; then
    echo "refusing: expected a commit SHA, got: '${REQ}'" >&2
    exit 64
fi
SHA="$REQ"
TAG="${SHA:0:7}"

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

# origin is GITLAB as of 2026-09-27 (read-only deploy key
# scoped to this project). The commit CI just built is therefore available
# immediately -- the deploy no longer waits on GitLab->GitHub mirror propagation,
# which is what it depended on when origin was the GitHub mirror.
echo "==> Fetching ${SHA}..."
if ! git fetch --quiet origin; then
    echo "refusing: git fetch from origin failed" >&2
    exit 65
fi

# Distinguish "the mirror has not propagated" from "the checkout was blocked".
# The first version of this script piped checkout's stderr to /dev/null and
# reported EVERY failure as a missing commit, which sent the first real deploy
# chasing a mirror problem that did not exist -- the actual error was a dirty
# working tree.
if ! git cat-file -e "${SHA}^{commit}" 2>/dev/null; then
    echo "refusing: commit ${SHA} is not on origin -- was it actually pushed?" >&2
    exit 65
fi

# A deploy's contract is "run exactly this commit", so local edits to TRACKED
# files are drift and get discarded. Silently preserving them is how this tree
# ended up 77 commits stale with scp'd files sitting on top of it. Untracked
# files (backups/, patches, this script) are NOT touched by checkout --force.
DRIFT="$(git status --porcelain --untracked-files=no || true)"
if [ -n "$DRIFT" ]; then
    echo "==> Discarding local modifications to tracked files:"
    echo "${DRIFT}" | sed 's/^/      /'
fi
git checkout --force --quiet --detach "${SHA}"
echo "==> Checked out $(git rev-parse --short=12 HEAD)"

echo "==> Pinning images to ${TAG}..."
# Re-pinned on every deploy on purpose: this .env is regenerated by the secrets
# export, which drops GHCR_OWNER/IMAGE_TAG and silently leaves compose resolving
# ${IMAGE_TAG:-latest}. Writing it immediately before `up` is what keeps the
# running stack on the tested tag.
touch .env
sed -i '/^GHCR_OWNER=/d;/^IMAGE_TAG=/d' .env
printf 'GHCR_OWNER=%s\nIMAGE_TAG=%s\n' "alcybersec" "${TAG}" >> .env

# Checked BEFORE pulling. A CI run died halfway through extracting the torch
# layer with "no space left on device" -- which surfaces as a containerd error
# naming a blob digest and reads like a registry fault, not a full disk. The
# host had almost no space free. Failing here instead costs a second and says what is
# actually wrong.
#
# 8G is the working figure: the api image carries torch, LibreOffice and the
# baked embedding model, and a pull needs room for the compressed layer AND its
# extracted form at once.
echo "==> Checking disk space..."
REQUIRED_GB=8
DOCKER_ROOT="$(docker info --format '{{.DockerRootDir}}' 2>/dev/null || echo /var/lib/docker)"
AVAIL_GB="$(( $(df -P -k "${DOCKER_ROOT}" | awk 'NR==2{print $4}') / 1024 / 1024 ))"
if [ "${AVAIL_GB}" -lt "${REQUIRED_GB}" ]; then
    echo "refusing: need ~${REQUIRED_GB}G free on ${DOCKER_ROOT} to pull and extract, have ${AVAIL_GB}G" >&2
    echo "  reclaim with:" >&2
    echo "    docker image prune -f   # then docker rmi old studyaio-api / studyaio-ui tags" >&2
    echo "    docker builder prune -af" >&2
    exit 66
fi
echo "    ${AVAIL_GB}G available on ${DOCKER_ROOT}"

echo "==> Pulling images..."
$COMPOSE pull --quiet

# SEC-06: an image that ships app/core/secret_box.py makes the api and worker
# refuse to start without SETTINGS_ENCRYPTION_KEY (unless SINGLE_USER_MODE=true).
# `up -d` would then crash-loop the api behind a "healthy" old stack that has
# already been stopped, and the usual cause is that .env was regenerated from
# the secret manager and the secret is missing there. So check the env the NEW image will
# actually get -- in a one-off container, so compose's own resolution (env_file,
# overlay, passthrough) is what is tested -- and abort before the dump,
# migration or any restart. Nothing is printed except a verdict: the key is a
# live secret and is never echoed. --no-deps: no db/redis needed; the one-off
# publishes no ports and starts no app code beyond this snippet.
echo "==> Checking SETTINGS_ENCRYPTION_KEY for the new image..."
# Presence is not enough (M32 N-4): a key that is set but malformed, or the
# well-known all-zero test key, crash-loops the new api exactly like a missing
# one. So the one-off runs the image's OWN startup check (secret_box.check_startup,
# the same call the api makes at boot) and then proves the key actually works with
# an encrypt/decrypt round trip on a throwaway string. Exit 1 = absent, 2 = set
# but rejected/unusable. Only the verdict and the (key-free) error text are printed.
KEY_RC=0
$COMPOSE run --rm --no-deps -T api python -c '
import importlib.util, os, sys
if importlib.util.find_spec("app.core.secret_box") is None:
    print("    image predates SEC-06; key not required")
    sys.exit(0)
if os.environ.get("SINGLE_USER_MODE", "").strip().lower() == "true":
    print("    SINGLE_USER_MODE=true; key not required")
    sys.exit(0)
if not os.environ.get("SETTINGS_ENCRYPTION_KEY", "").strip():
    sys.exit(1)
try:
    from app.core import secret_box
    secret_box.check_startup()
    probe = "deploy-key-probe"
    if secret_box.decrypt(secret_box.encrypt(probe)) != probe:
        raise RuntimeError("encrypt/decrypt round trip did not return the input")
except Exception as exc:
    print(f"    key rejected: {type(exc).__name__}: {exc}")
    sys.exit(2)
print("    SETTINGS_ENCRYPTION_KEY is present and works (startup check + round trip)")
' || KEY_RC=$?
if [ "${KEY_RC}" -eq 1 ]; then
    echo "refusing: this image requires SETTINGS_ENCRYPTION_KEY and the environment has none." >&2
    echo "  The api and worker would crash-loop at startup. Nothing was dumped, migrated or restarted." >&2
    echo "  Add the secret to the secret manager (see docs/deployment.md, SETTINGS_ENCRYPTION_KEY), re-export .env, and redeploy." >&2
    exit 68
elif [ "${KEY_RC}" -eq 2 ]; then
    echo "refusing: SETTINGS_ENCRYPTION_KEY is set but the new image rejects it (malformed, test key, or unusable)." >&2
    echo "  Nothing was dumped, migrated or restarted. Fix the secret, re-export .env, and redeploy." >&2
    exit 68
elif [ "${KEY_RC}" -ne 0 ]; then
    echo "refusing: could not run the SETTINGS_ENCRYPTION_KEY check (exit ${KEY_RC}); not continuing blind" >&2
    exit 68
fi

# Migrate BEFORE any new app container exists. On the !34 deploy (2026-10-10,
# R-028) `up -d` started the new worker/beat first, the hourly beat fired at once
# and its tasks failed with "column user_settings.timezone does not exist" for the
# ~5s until the old `exec ... alembic upgrade head` ran.
#
# So: bring up only the data tier (idempotent, no-op when already running, --wait
# blocks on its healthchecks), then run alembic in a ONE-OFF container from the
# NEW api image (--no-deps: db/redis are already up; the one-off publishes no
# ports). The OLD api/worker/beat/ui keep serving meanwhile. set -e means a failed
# migration aborts here and leaves the old stack untouched. This relies on
# migrations being additive/backwards-compatible for one release; see
# docs/deployment.md.
echo "==> Ensuring db and redis are up..."
$COMPOSE up -d --no-build --wait db redis

# Dump BEFORE migrating (GL#24 / TECH-06): a migration is the one step that can
# damage data in place, and until now a deploy took no backup of its own. The
# dump is gzip-compressed, timestamped, written via .partial and renamed only on
# success, and a failure (pg_dump error, empty file, gzip -t failing) aborts the
# deploy here -- set -e plus the explicit exit -- with the old stack untouched.
# pg_dump runs INSIDE the db container (server-matched version, no host client
# needed); credentials come from the container's own POSTGRES_* env, never argv.
# Dumps land in backups/ (untracked, survives `checkout --force`) alongside the
# beat backups; keep the newest PREDEPLOY_KEEP of them (default 7).
echo "==> Dumping database before migration..."
PREDEPLOY_KEEP="${PREDEPLOY_KEEP:-7}"
mkdir -p backups
DUMP="backups/predeploy_$(date +%Y%m%d_%H%M%S)_${TAG}.sql.gz"
if ! $COMPOSE exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "${DUMP}.partial" \
        || [ "$(stat -c %s "${DUMP}.partial")" -lt 100 ] \
        || ! gzip -t "${DUMP}.partial"; then
    rm -f "${DUMP}.partial"
    echo "refusing: pre-migration database dump failed; nothing was migrated or restarted" >&2
    exit 67
fi
mv "${DUMP}.partial" "${DUMP}"
echo "    ${DUMP} ($(du -h "${DUMP}" | cut -f1))"
# Retention: only this script's own predeploy_* files, newest N kept.
ls -1t backups/predeploy_*.sql.gz 2>/dev/null | tail -n +"$((PREDEPLOY_KEEP + 1))" | while read -r old; do
    rm -f -- "$old"
done

echo "==> Running migrations (one-off container, new image)..."
$COMPOSE run --rm --no-deps -T api alembic upgrade head

echo "==> Starting containers..."
$COMPOSE up -d --no-build --remove-orphans

echo "==> Verifying health..."
sleep 5
$COMPOSE exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready')"
curl -fsS -o /dev/null "http://localhost:${UI_PORT:-3001}/"

# TECH-09 (GL#51): three Celery pools, one per queue family. A pool that failed to
# boot would leave its queue unconsumed -- uploads stuck, or beat jobs piling up --
# with api and ui both healthy, so ping each node by name. Retried because a worker
# needs a few seconds after `up -d` before it answers.
for pool in pipeline:worker ondemand:worker-ondemand maintenance:worker-maintenance; do
    node="${pool%%:*}"; svc="${pool##*:}"
    ok=0
    for _ in 1 2 3 4 5 6; do
        if $COMPOSE exec -T "$svc" sh -c "celery -A app.worker:celery_app inspect ping -d ${node}@\$HOSTNAME --timeout 5" >/dev/null 2>&1; then
            ok=1; break
        fi
        sleep 5
    done
    if [ "$ok" -ne 1 ]; then
        echo "refusing to call this deploy healthy: Celery node ${node}@ (service ${svc}) did not answer a ping" >&2
        exit 69
    fi
    echo "    celery ${node}: ok"
done

# Retention is by RELEASE, not by age. The previous rule (`prune -af --filter
# until=168h`) kept every image younger than a week; at ~4.5G per api image on a
# 30G disk, four or five recent tags filled it and the NEXT deploy was refused
# by the disk guard above. Now: keep the release that is running (this one) and
# the previous KEEP_RELEASES-1 (default: one rollback target), untag every other
# app image regardless of age, and leave non-app images alone. Anything dropped
# is re-pullable from GHCR. Images used by a container are never removed.
echo "==> Pruning old images (keeping ${KEEP_RELEASES} release(s))..."
prune_old_app_images "${KEEP_RELEASES}" "${TAG}" "alcybersec"
docker builder prune -af >/dev/null 2>&1 || true

echo "==> Deploy complete: ${SHA} (tag ${TAG})"

#!/usr/bin/env bash
#
# Pull-based deploy. Run on a systemd timer (deploy/glucolog-redeploy.timer);
# see deploy/README.md for installation.
#
# Checks GHCR for a newer image published by CI, and the deploy branch for
# changed compose/proxy config. Restarts the app only when something actually
# changed, so the timer is free to run often and stay silent.
#
# Deliberately pull-based: nothing inbound is opened, and no VM SSH key has to
# live in GitHub Secrets.
set -euo pipefail

cd /opt/glucolog

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)
BRANCH="${GLUCOLOG_BRANCH:-dev}"
IMAGE="ghcr.io/vedranchi/glucolog:${GLUCOLOG_TAG:-dev}"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

changed=0

# --- config: compose files, Caddyfile, deploy scripts ---------------------
# --ff-only so a surprise divergence fails loudly instead of auto-merging on a
# production host. .env and email.env are gitignored and untouched by this.
config_before="$(git rev-parse HEAD)"
git fetch --quiet origin "$BRANCH"
if ! git merge --ff-only --quiet "origin/$BRANCH" 2>/dev/null; then
    log "ERROR: cannot fast-forward to origin/$BRANCH — the VM checkout has diverged."
    log "       Resolve by hand in /opt/glucolog; leaving the running app alone."
    exit 1
fi
config_after="$(git rev-parse HEAD)"

if [ "$config_before" != "$config_after" ]; then
    log "config updated: ${config_before:0:7} -> ${config_after:0:7}"
    changed=1
fi

# --- image: whatever CI last published ------------------------------------
image_before="$(docker image inspect "$IMAGE" --format '{{.Id}}' 2>/dev/null || echo none)"
if ! "${COMPOSE[@]}" pull --quiet web; then
    log "ERROR: could not pull $IMAGE — leaving the running app alone."
    exit 1
fi
image_after="$(docker image inspect "$IMAGE" --format '{{.Id}}')"

if [ "$image_before" != "$image_after" ]; then
    log "new image: ${image_before#sha256:} -> ${image_after#sha256:}"
    changed=1
fi

if [ "$changed" -eq 0 ]; then
    exit 0
fi

# The container runs migrate + collectstatic on boot, so `up -d` is the whole
# deploy. Caddy retries a cold upstream, so it needs no restart.
log "redeploying web"
"${COMPOSE[@]}" up -d web

# Untagged parents of the image we just replaced. Disk is cheap here (39G free)
# but an unbounded image history on a free-tier box is not.
docker image prune -f --filter "dangling=true" > /dev/null

log "deploy complete: $("${COMPOSE[@]}" ps --format '{{.Name}} {{.Status}}' web)"

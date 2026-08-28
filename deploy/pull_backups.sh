#!/usr/bin/env bash
#
# Pull Glucolog Postgres backups from the Oracle VM down to this machine.
#
# deploy/backup.sh already runs on the VM (cron, nightly) and verifies each
# dump before keeping it. Backups still live only on that VM until this runs,
# so losing the instance would take the backups with it -- this closes that
# gap by rsyncing them to a second machine.
#
# Run manually, or scheduled via
# ~/Library/LaunchAgents/com.glucolog.pullbackups.plist (see deploy/README.md).

set -euo pipefail

SSH_KEY="${GLUCOLOG_SSH_KEY:-$HOME/.ssh/ssh-key-2026-08-20.key}"
VM_HOST="ubuntu@89.168.119.75"
REMOTE_DIR="/opt/glucolog/backups/"
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/backups/"

mkdir -p "$LOCAL_DIR"

rsync -az -e "ssh -i $SSH_KEY -o ConnectTimeout=10 -o BatchMode=yes" \
  "$VM_HOST:$REMOTE_DIR" "$LOCAL_DIR"

COUNT="$(find "$LOCAL_DIR" -name 'glucolog-*.sql.gz' -type f | wc -l | tr -d ' ')"
echo "[pull-backups] $(date -u +%FT%TZ) synced -- $COUNT dump(s) now local in $LOCAL_DIR"

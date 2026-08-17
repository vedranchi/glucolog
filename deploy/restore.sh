#!/usr/bin/env bash
#
# Restore a Glucolog database dump.
#
#   ./deploy/restore.sh backups/glucolog-<stamp>.sql.gz --into drill_db
#       Restore into a scratch database. Non-destructive: this is how you
#       verify a backup is actually restorable without touching live data.
#
#   ./deploy/restore.sh backups/glucolog-<stamp>.sql.gz
#       Restore over the LIVE database. Destructive. Requires typing the
#       database name to confirm.
#
# A backup that has never been restored is not a backup. Run the drill.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

COMPOSE="${COMPOSE:--f docker-compose.yml -f docker-compose.prod.yml}"

DUMP="${1:-}"
TARGET_DB=""
if [ "${2:-}" = "--into" ]; then
  TARGET_DB="${3:?--into needs a database name}"
fi

if [ -z "$DUMP" ] || [ ! -f "$DUMP" ]; then
  echo "usage: $0 <dump.sql.gz> [--into <scratch_db>]" >&2
  exit 1
fi

if ! gzip -t "$DUMP" 2>/dev/null; then
  echo "refusing to restore: $DUMP is not valid gzip" >&2
  exit 1
fi

# shellcheck disable=SC2086
compose_db() { docker compose $COMPOSE exec -T db "$@"; }

LIVE_DB="$(compose_db sh -c 'printf %s "$POSTGRES_DB"')"

if [ -z "$TARGET_DB" ]; then
  TARGET_DB="$LIVE_DB"
  echo
  echo "  *** DESTRUCTIVE ***"
  echo "  About to restore $DUMP over the LIVE database '$LIVE_DB'."
  echo "  Existing data will be dropped and replaced."
  echo
  printf "  Type the database name to continue: "
  read -r CONFIRM
  if [ "$CONFIRM" != "$LIVE_DB" ]; then
    echo "  aborted" >&2
    exit 1
  fi
else
  echo "[restore] drill mode: restoring into scratch database '$TARGET_DB'"
  echo "[restore] live database '$LIVE_DB' will not be touched"
  compose_db sh -c \
    "PGPASSWORD=\"\$POSTGRES_PASSWORD\" psql -U \"\$POSTGRES_USER\" -d postgres -v ON_ERROR_STOP=1 \
       -c 'DROP DATABASE IF EXISTS \"$TARGET_DB\";' \
       -c 'CREATE DATABASE \"$TARGET_DB\";'" >/dev/null
fi

echo "[restore] restoring $DUMP -> $TARGET_DB"
gunzip -c "$DUMP" | compose_db sh -c \
  "PGPASSWORD=\"\$POSTGRES_PASSWORD\" psql -U \"\$POSTGRES_USER\" -d \"$TARGET_DB\" -q" >/dev/null

echo "[restore] verifying restored contents"
compose_db sh -c \
  "PGPASSWORD=\"\$POSTGRES_PASSWORD\" psql -U \"\$POSTGRES_USER\" -d \"$TARGET_DB\" -tA -c \
   \"SELECT 'users=' || (SELECT count(*) FROM users_user)
          || ' glucose=' || (SELECT count(*) FROM logs_glucoselog)
          || ' insulin=' || (SELECT count(*) FROM logs_insulinlog)
          || ' meals='   || (SELECT count(*) FROM logs_meallog);\""

echo "[restore] done"

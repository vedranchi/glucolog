#!/usr/bin/env bash
#
# Dump the GlucoRead Postgres database to a compressed, timestamped file.
#
# Intended to run from cron on the VM. See deploy/README.md for the crontab
# entry and the restore procedure.
#
#   ./deploy/backup.sh                 # prod (default)
#   COMPOSE="-f docker-compose.yml" ./deploy/backup.sh   # dev
#
# Credentials are never passed from the host: pg_dump runs inside the db
# container and reads the POSTGRES_* variables already present there.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

BACKUP_DIR="${BACKUP_DIR:-$REPO_DIR/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
COMPOSE="${COMPOSE:--f docker-compose.yml -f docker-compose.prod.yml}"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TARGET="$BACKUP_DIR/glucolog-$STAMP.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[backup] $(date -u +%FT%TZ) dumping to $TARGET"

# --clean --if-exists makes the dump self-contained: restoring it drops and
# recreates objects rather than colliding with whatever is already there.
# shellcheck disable=SC2086
docker compose $COMPOSE exec -T db sh -c \
  'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  | gzip -9 > "$TARGET"

# Verify before trusting it. A dump that failed midway still leaves a file, and
# rotating on the strength of a broken backup is how backup histories quietly
# disappear.
if ! gzip -t "$TARGET" 2>/dev/null; then
  echo "[backup] FAILED: $TARGET is not valid gzip — keeping older backups" >&2
  rm -f "$TARGET"
  exit 1
fi

if ! gunzip -c "$TARGET" | grep -q "PostgreSQL database dump complete"; then
  echo "[backup] FAILED: dump is truncated — keeping older backups" >&2
  rm -f "$TARGET"
  exit 1
fi

# Sanity-check that real tables are present, so an empty-but-valid dump of the
# wrong database cannot pass as a good backup.
for table in users_user logs_glucoselog logs_insulinlog logs_meallog; do
  if ! gunzip -c "$TARGET" | grep -q "$table"; then
    echo "[backup] FAILED: table $table missing from dump — keeping older backups" >&2
    rm -f "$TARGET"
    exit 1
  fi
done

SIZE="$(du -h "$TARGET" | cut -f1)"
echo "[backup] ok: $TARGET ($SIZE)"

# Rotation happens only after the new dump has been verified above.
DELETED="$(find "$BACKUP_DIR" -name 'glucolog-*.sql.gz' -type f -mtime "+$RETENTION_DAYS" -print -delete | wc -l | tr -d ' ')"
echo "[backup] retention ${RETENTION_DAYS}d: removed $DELETED old backup(s), $(find "$BACKUP_DIR" -name 'glucolog-*.sql.gz' -type f | wc -l | tr -d ' ') remaining"

# Offsite copy — best-effort. .env.backup is optional and gitignored, same as
# .env; its absence just means no offsite target is configured on this
# machine yet. A push failure does not fail the job: the local dump above is
# already verified and safe, so a network hiccup here shouldn't page anyone.
ENV_BACKUP="$REPO_DIR/.env.backup"
if [ -f "$ENV_BACKUP" ] && command -v rclone >/dev/null 2>&1; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_BACKUP"
  set +a
  if [ -n "${B2_BUCKET:-}" ]; then
    if rclone copy "$BACKUP_DIR" "b2glucolog:${B2_BUCKET}" >/dev/null 2>&1; then
      echo "[backup] offsite: synced to B2 bucket $B2_BUCKET"
    else
      echo "[backup] WARNING: offsite sync to B2 failed — local backup is still ok" >&2
    fi
  fi
fi

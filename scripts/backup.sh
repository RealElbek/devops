#!/usr/bin/env bash
# Dump the Postgres database to backups/<db>-<timestamp>.dump (pg_dump custom format, compressed).
# The dump is checked with pg_restore --list, then only the newest BACKUP_KEEP files are kept.
# Usage: ./scripts/backup.sh [OUTPUT_FILE]      env: BACKUP_DIR (default backups), BACKUP_KEEP (default 7)
set -euo pipefail
cd "$(dirname "$0")/.."

BACKUP_DIR="${BACKUP_DIR:-backups}"
BACKUP_KEEP="${BACKUP_KEEP:-7}"

if ! docker compose exec -T db pg_isready -q 2>/dev/null; then
  echo "ERROR: db container is not running or not ready (try: make up)" >&2
  exit 1
fi

# Credentials come from the container's own env, so nothing secret appears on the host command line.
db_name=$(docker compose exec -T db sh -c 'echo "$POSTGRES_DB"')
mkdir -p "$BACKUP_DIR"
out="${1:-$BACKUP_DIR/$db_name-$(date +%Y%m%d-%H%M%S).dump}"
tmp="$out.partial"
trap 'rm -f "$tmp"' EXIT

echo "Backing up database '$db_name' -> $out"
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$tmp"

# A dump that pg_restore can't read is not a backup.
if ! docker compose exec -T db pg_restore --list < "$tmp" > /dev/null; then
  echo "ERROR: backup file is not a valid dump, not keeping it" >&2
  exit 1
fi
mv "$tmp" "$out"
echo "OK  $(du -h "$out" | cut -f1)  $out"

# Rotation: only automatic <db>-*.dump names, newest first. pre-restore-*.dump files are never auto-deleted.
if [ -z "${1:-}" ] && [ "$BACKUP_KEEP" -gt 0 ]; then
  ls -1t "$BACKUP_DIR"/"$db_name"-*.dump 2>/dev/null | tail -n +"$((BACKUP_KEEP + 1))" | while read -r old; do
    echo "Removing old backup $old"
    rm -f "$old"
  done
fi

#!/usr/bin/env bash
# Restore the database from a dump made by backup.sh. REPLACES all current data.
#   1. takes a safety backup of the current data (backups/pre-restore-*.dump)
#   2. stops the app so no requests write during the restore
#   3. pg_restore --clean in ONE transaction: if anything fails, the old data stays as it was
#   4. starts the app again and waits until everything is healthy
# Usage: ./scripts/restore.sh FILE     (latest backup if FILE is omitted; YES=1 skips the prompt)
set -euo pipefail
cd "$(dirname "$0")/.."

BACKUP_DIR="${BACKUP_DIR:-backups}"
file="${1:-$(ls -1t "$BACKUP_DIR"/*.dump 2>/dev/null | grep -v '/pre-restore-' | head -n 1 || true)}"

if [ -z "$file" ] || [ ! -f "$file" ]; then
  echo "ERROR: backup file not found: ${file:-<none in $BACKUP_DIR/>}" >&2
  echo "Usage: make restore FILE=backups/<name>.dump    (list: ls -lt $BACKUP_DIR)" >&2
  exit 1
fi

if ! docker compose exec -T db pg_isready -q 2>/dev/null; then
  echo "ERROR: db container is not running or not ready (try: docker compose up -d --wait db)" >&2
  exit 1
fi

if ! docker compose exec -T db pg_restore --list < "$file" > /dev/null; then
  echo "ERROR: $file is not a valid pg_dump custom-format file" >&2
  exit 1
fi

db_name=$(docker compose exec -T db sh -c 'echo "$POSTGRES_DB"')
echo "This will REPLACE all data in database '$db_name' with $file"
if [ "${YES:-}" != 1 ]; then
  read -r -p "Type 'yes' to continue: " answer
  [ "$answer" = yes ] || { echo "Aborted."; exit 1; }
fi

safety="$BACKUP_DIR/pre-restore-$(date +%Y%m%d-%H%M%S).dump"
echo "1/4 Safety backup of current data -> $safety"
BACKUP_KEEP=0 ./scripts/backup.sh "$safety"

echo "2/4 Stopping app (no writes during restore)"
docker compose stop app

restart_app() { echo "4/4 Starting app"; docker compose up -d --wait --wait-timeout 180; }
trap 'echo "Restore FAILED, old data is unchanged (single transaction)." >&2; restart_app' ERR

echo "3/4 Restoring $file"
docker compose exec -T db sh -c \
  'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --single-transaction --exit-on-error' \
  < "$file"

trap - ERR
restart_app
echo "Restore complete. Previous data saved in $safety"

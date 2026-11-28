#!/usr/bin/env bash
# Restore all 4 microservice databases from a backup folder made by backup.sh. REPLACES all data.
#   1. checks that all 4 dump files exist and are valid (before touching anything)
#   2. asks for 'yes'
#   3. safety backup of the current data -> backups/pre-restore-<timestamp>/
#   4. stops the 4 microservices so nothing writes during the restore
#   5. restores each database with pg_restore --clean --single-transaction
#   6. starts everything again and waits until healthy
#
# NOTE: each database is restored in its own transaction (all-or-nothing per database), but the
# 4 databases together are NOT one transaction. If database 3 fails, databases 1-2 are already
# restored. The script stops, says which ones were restored, and the safety backup from step 3
# is how to go back: make restore FILE=backups/pre-restore-<timestamp>
#
# Usage: ./scripts/restore.sh [BACKUP_FOLDER]   (newest backup if omitted; YES=1 skips the prompt)
set -Eeuo pipefail   # -E: the ERR trap also fires for failures inside functions (dbx)
cd "$(dirname "$0")/.."
. scripts/db_lib.sh

dir="${1:-$(list_backups | head -n 1)}"
dir="${dir%/}"
if [ -z "$dir" ] || [ ! -d "$dir" ]; then
  echo "ERROR: backup folder not found: ${dir:-<none in $BACKUP_DIR/>}" >&2
  echo "Usage: make restore FILE=backups/<YYYYMMDD-HHMMSS>    (list: ls $BACKUP_DIR)" >&2
  exit 1
fi

require_dbs_ready

# 1. Check every file BEFORE changing anything.
echo "Checking backup $dir/"
problems=""
for svc in $DB_SERVICES; do
  db=$(db_name "$svc")
  file="$dir/$db.dump"
  if [ ! -f "$file" ]; then
    problems="$problems\n  missing: $file"
  elif ! dbx "$svc" pg_restore --list < "$file" > /dev/null 2>&1; then
    problems="$problems\n  not a valid dump: $file"
  else
    echo "  OK  $db.dump"
  fi
done
if [ -n "$problems" ]; then
  printf "ERROR: backup is incomplete or broken, nothing was changed:$problems\n" >&2
  exit 1
fi

# 2. Confirm.
echo "This will REPLACE all data in the 4 databases (events, bookings, payments, tickets) with $dir/"
if [ "${YES:-}" != 1 ]; then
  read -r -p "Type 'yes' to continue: " answer || answer=""
  [ "$answer" = yes ] || { echo "Aborted."; exit 1; }
fi

# 3. Safety backup.
safety="$BACKUP_DIR/pre-restore-$(date +%Y%m%d-%H%M%S)"
echo "1/4 Safety backup of current data -> $safety/"
BACKUP_KEEP=0 ./scripts/backup.sh "$safety"

# 4. Stop the microservices (the databases keep running).
apps=""
for svc in $DB_SERVICES; do apps="$apps $svc-service"; done
echo "2/4 Stopping microservices:$apps"
docker compose stop $apps

restart_all() { echo "4/4 Starting everything"; docker compose up -d --wait --wait-timeout 180; }
restored=""
current=""
on_error() {
  trap - ERR
  echo >&2
  echo "Restore FAILED while restoring $current." >&2
  echo "  $current is unchanged (its restore runs in one transaction)." >&2
  echo "  Already restored from the backup:${restored:- none}" >&2
  echo "  The databases are now from different points in time. To go back to the data before" >&2
  echo "  this restore, run:  make restore FILE=$safety" >&2
  restart_all
}
trap on_error ERR

# 5. Restore each database in its own transaction.
echo "3/4 Restoring databases"
for svc in $DB_SERVICES; do
  db=$(db_name "$svc")
  current="$svc-db"
  echo "  $svc-db <- $dir/$db.dump"
  dbx "$svc" sh -c \
    'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --single-transaction --exit-on-error' \
    < "$dir/$db.dump"
  restored="$restored $svc-db"
done

trap - ERR
restart_all
echo "Restore complete. Previous data saved in $safety/"

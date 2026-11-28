#!/usr/bin/env bash
# Back up all 4 microservice databases into ONE folder:
#   backups/<YYYYMMDD-HHMMSS>/events.dump, bookings.dump, payments.dump, tickets.dump
# Each dump is pg_dump custom format (compressed) and is checked with pg_restore --list.
# The folder only appears when ALL dumps are good (written to <folder>.partial first).
# Then only the newest BACKUP_KEEP backup folders are kept.
# Usage: ./scripts/backup.sh [OUTPUT_DIR]      env: BACKUP_DIR (default backups), BACKUP_KEEP (default 7)
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/db_lib.sh

BACKUP_KEEP="${BACKUP_KEEP:-7}"

require_dbs_ready

out="${1:-$BACKUP_DIR/$(date +%Y%m%d-%H%M%S)}"
out="${out%/}"
if [ -e "$out" ]; then
  echo "ERROR: $out already exists, not overwriting it" >&2
  exit 1
fi
tmp="$out.partial"
rm -rf "$tmp"
mkdir -p "$tmp"
trap 'rm -rf "$tmp"' EXIT

echo "Backing up 4 databases -> $out/"
for svc in $DB_SERVICES; do
  db=$(db_name "$svc")
  file="$tmp/$db.dump"
  dbx "$svc" sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' < /dev/null > "$file"
  # A dump that pg_restore can't read is not a backup.
  if ! dbx "$svc" pg_restore --list < "$file" > /dev/null; then
    echo "ERROR: dump of $svc-db ($db) is not valid, backup not kept" >&2
    exit 1
  fi
  printf '  OK  %-11s -> %-15s %s\n' "$svc-db" "$db.dump" "$(du -h "$file" | cut -f1)"
done

mv "$tmp" "$out"
trap - EXIT
echo "Backup complete: $out/"

# Rotation: only timestamped folders (never pre-restore-*), only for automatic names.
if [ -z "${1:-}" ] && [ "$BACKUP_KEEP" -gt 0 ]; then
  list_backups | tail -n +"$((BACKUP_KEEP + 1))" | while read -r old; do
    echo "Removing old backup $old/"
    rm -rf "$old"
  done
fi

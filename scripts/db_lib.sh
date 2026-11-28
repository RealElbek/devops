# Shared by backup.sh and restore.sh (source it, don't run it).
# Every microservice owns one Postgres container named <svc>-db, e.g. booking-db.
# Plain strings, not arrays: works on macOS bash 3.2 and Linux bash 5.

DB_SERVICES="event booking payment ticket"
BACKUP_DIR="${BACKUP_DIR:-backups}"

# Run a command inside <svc>-db. Credentials come from the container's own env
# ($POSTGRES_USER, $POSTGRES_DB), so nothing secret appears on the host command line.
dbx() { local svc=$1; shift; docker compose exec -T "$svc-db" "$@"; }

# Database name of a service, e.g. booking -> bookings
db_name() { dbx "$1" sh -c 'echo "$POSTGRES_DB"' < /dev/null; }   # </dev/null: don't eat the user's input

# Stop with a clear message if any database container is not running/ready.
require_dbs_ready() {
  local svc down=""
  for svc in $DB_SERVICES; do
    dbx "$svc" pg_isready -q < /dev/null > /dev/null 2>&1 || down="$down $svc-db"
  done
  if [ -n "$down" ]; then
    echo "ERROR: database container(s) not running or not ready:$down" >&2
    echo "       start them with: make up   (or: docker compose up -d --wait$down)" >&2
    exit 1
  fi
}

# Timestamped backup folders (YYYYMMDD-HHMMSS), newest first. pre-restore-* folders are not listed.
list_backups() {
  local d
  for d in "$BACKUP_DIR"/*/; do
    d="${d%/}"
    case "${d##*/}" in
      [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9]) echo "$d" ;;
    esac
  done | sort -r
}

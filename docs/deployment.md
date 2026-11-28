# Deployment & operations

## Requirements
Docker 24+ with Compose v2. ~1 GB free RAM. Ports 80 and 8080 free (change in `.env`).

## Configuration (`.env`)

| Variable | Default | Meaning |
| -------- | ------- | ------- |
| `EVENT_DB_PASS`, `BOOKING_DB_PASS`, `PAYMENT_DB_PASS`, `TICKET_DB_PASS` | from `.env.example` | One password per service database — **change on a real server** |
| `HTTP_PORT` | 80 | Host port for the gateway |
| `CADVISOR_PORT` | 8080 | Host port for cAdvisor |
| `HOLD_MINUTES` | 10 | How long unpaid seats stay reserved |
| `SEED_DEMO` | true | Create one demo event on first start |
| `LOG_LEVEL` | INFO | Log level of every service |

Compose stops with an error if any `*_DB_PASS` is missing (`${EVENT_DB_PASS:?...}`).

> **Upgrading from the old single-service version?** Its `.env` has `DB_USER`/`DB_PASS`. Add the
> four `*_DB_PASS` lines from `.env.example`, then `make up` (old `app`/`db` containers are removed
> automatically with `--remove-orphans`; the old `pgdata` volume is no longer used).

## Everyday commands

```sh
make up            # build + start + wait for healthy
make ps            # status and health of every container
make logs          # follow gateway + all service logs
make test          # ruff + pytest for every service, each against its own Postgres
make test SERVICE=booking   # only one service
make smoke         # end-to-end booking through the gateway (all 4 services)
make resilience    # persistence, scaling, fault isolation
make scale         # 3 booking-service replicas
make down          # stop, keep data
make clean         # stop and DELETE data
```

## Production hardening in this stack

| Practice | Where |
| -------- | ----- |
| Restart policy `unless-stopped` | every long-running service |
| Healthchecks + `depends_on: service_healthy` | every database, service and the gateway |
| Resource limits (CPU / memory) | `x-postgres`, `x-service` anchors + gateway |
| Non-root user, read-only filesystem, `cap_drop: ALL`, `no-new-privileges` | all 4 services (`x-service`) |
| Internal networks (no internet, no host access) | `backend` + one `*-data` network per database |
| Only the gateway + cAdvisor publish ports; `/internal/*` not routed | compose `ports:`, `nginx.conf` |
| Log rotation (10 MB × 3 files) | `x-logging` |
| Rate limiting (20 r/s per IP, burst 40) | nginx |
| Secrets only in `.env` (git-ignored) + gitleaks in CI | `.gitignore`, `ci.yml` |
| Pinned image and package versions, Dependabot | each service's Dockerfile + requirements, `.github/dependabot.yml` |

## Backup and restore

> ⚠️ **To be updated for microservices.** These scripts were written for the single `db`
> container. With one database per service they must back up and restore `event-db`,
> `booking-db`, `payment-db` and `ticket-db`. Until then `make backup` stops with
> "no such service: db" (it does not silently back up the wrong thing).

```sh
make backup                                   # -> backups/ticketing-YYYYMMDD-HHMMSS.dump
make restore                                  # restore the newest backup (asks for 'yes')
make restore FILE=backups/ticketing-20261128-140229.dump
YES=1 make restore FILE=...                   # no prompt (scripts / cron)
```

- **Format**: `pg_dump -Fc` (compressed, restored with `pg_restore`). Each dump is checked with
  `pg_restore --list` before it is kept, so a broken dump never replaces a good one.
- **Rotation**: `make backup` keeps the newest 7 (`BACKUP_KEEP=14 make backup` to change).
  `backups/` is git-ignored — copy dumps off the machine for real disaster recovery.
- **Restore is safe to retry**: it first saves the current data to `backups/pre-restore-*.dump`
  (never auto-deleted), stops the app so nothing writes, and restores in **one transaction**
  (`--single-transaction --exit-on-error`): if anything fails, the old data is untouched. Then it
  starts the app and waits until every container is healthy.
- If you ran `make scale`, restore brings the app back to 1 replica; run `make scale` again.
- Credentials are read inside the db container (`$POSTGRES_USER`), never passed on the host command line.

Nightly backup with cron (Linux server):

```sh
0 3 * * * cd /opt/devops && ./scripts/backup.sh >> backups/backup.log 2>&1
```

## Troubleshooting

| Symptom | Check | Fix |
| ------- | ----- | --- |
| `make up` hangs on a service | `docker compose logs booking-service` | DB password wrong in `.env`; `make clean` if you changed it after first start |
| `/health/booking` returns 503 | `docker compose ps booking-db` | `docker compose start booking-db`: the service reconnects by itself |
| `{"error": "event-service unavailable"}` | `docker compose ps event-service` | start it again; other services keep working meanwhile |
| Port 80 already in use | `lsof -i :80` | set `HTTP_PORT=8000` in `.env` |
| 429 Too Many Requests | nginx rate limit | slow down, or raise `rate=` in `nginx/nginx.conf` |
| cAdvisor shows little data on macOS | Docker Desktop runs in a VM | expected; full metrics on Linux |

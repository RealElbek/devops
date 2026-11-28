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
| Image scan: CI fails on fixable HIGH/CRITICAL vulnerabilities (OS + Python packages) | `ci.yml` job "Image scan (Trivy)" |
| OS security updates on top of the base image (`apt-get upgrade`) | each service `Dockerfile` |
| Pinned image and package versions, Dependabot | each service's Dockerfile + requirements, `.github/dependabot.yml` |

## Images on GitHub Container Registry

After every merge to `main` that passes all checks, CI job **Publish images (GHCR)** pushes:

```
ghcr.io/realelbek/ticketing-event-service     :latest  :sha-<7-char commit>
ghcr.io/realelbek/ticketing-booking-service   :latest  :sha-<7-char commit>
ghcr.io/realelbek/ticketing-payment-service   :latest  :sha-<7-char commit>
ghcr.io/realelbek/ticketing-ticket-service    :latest  :sha-<7-char commit>
```

- Use the `sha-…` tag to deploy or roll back to an exact, tested commit; `latest` = newest `main`.
- Only the publish job has `packages: write`; pull requests never publish.
- Images are linked to this repo by the `org.opencontainers.image.source` label in each Dockerfile.
- Pull: `docker pull ghcr.io/realelbek/ticketing-booking-service:latest` (log in with
  `docker login ghcr.io` first if the package is private).

## Backup and restore

Every microservice owns its own database, so a backup is **one folder with 4 dumps**:

```
backups/20261128-150000/
  events.dump     <- event-db   (events, seats)
  bookings.dump   <- booking-db (bookings, booking_seats)
  payments.dump   <- payment-db (payments)
  tickets.dump    <- ticket-db  (tickets)
```

```sh
make backup                                   # -> backups/YYYYMMDD-HHMMSS/ with 4 dumps
make restore                                  # restore the newest backup folder (asks for 'yes')
make restore FILE=backups/20261128-150000     # restore a specific folder
YES=1 make restore FILE=...                   # no prompt (scripts / cron)
```

**`make backup`** ([scripts/backup.sh](../scripts/backup.sh))

- Loops over `event booking payment ticket` and runs `pg_dump -Fc` (compressed custom format)
  inside each `<svc>-db` container.
- Each dump is checked with `pg_restore --list`. Dumps are written to `<folder>.partial/` and the
  folder is only renamed to its final name when **all 4** are good, so a half-finished backup never
  looks like a real one.
- Stops with a clear error if any database container is down (it does not save 3 of 4).
- **Rotation**: keeps the newest 7 backup folders (`BACKUP_KEEP=14 make backup` to change).
  `pre-restore-*` folders are never deleted automatically.

**`make restore`** ([scripts/restore.sh](../scripts/restore.sh))

1. Checks all 4 files exist and are valid dumps. If any is missing or broken, it stops **before
   changing anything**.
2. Asks you to type `yes`.
3. Saves a **safety backup** of the current data to `backups/pre-restore-<timestamp>/`.
4. Stops the 4 microservices (`event-service booking-service payment-service ticket-service`) so
   nothing writes during the restore. The databases keep running.
5. Restores each database with `pg_restore --clean --if-exists --single-transaction --exit-on-error`.
6. Starts everything again and waits until every container is healthy.

> ⚠️ **What is (and is not) atomic.** Each database is restored in **one transaction**: if its
> restore fails, that database is left exactly as it was. But the **4 databases together are not
> one transaction**, because they are separate Postgres servers. If, for example, `ticket-db` fails,
> `event-db`, `booking-db` and `payment-db` are already restored, and the data is from different
> points in time. The script stops, prints which databases were restored, starts the services
> again, and tells you how to go back:
>
> ```sh
> make restore FILE=backups/pre-restore-<timestamp>
> ```
>
> That safety backup is the way to undo a partial restore.

Other notes:

- Credentials are read inside each database container (`$POSTGRES_USER`, `$POSTGRES_DB`), never
  passed on the host command line.
- `backups/` is git-ignored (dumps contain customer data). Copy backup folders off the machine for
  real disaster recovery.
- If you ran `make scale`, restore brings booking-service back to 1 replica; run `make scale` again.
- Backups from before the microservices split (single `ticketing-*.dump` files) cannot be restored
  with these scripts.

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

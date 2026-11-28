# Deployment & operations

## Requirements
Docker 24+ with Compose v2. ~1 GB free RAM. Ports 80 and 8080 free (change in `.env`).

## Configuration (`.env`)

| Variable | Default | Meaning |
| -------- | ------- | ------- |
| `DB_USER` / `DB_PASS` / `DB_NAME` | from `.env.example` | Postgres credentials — **change on a real server** |
| `HTTP_PORT` | 80 | Host port for nginx |
| `CADVISOR_PORT` | 8080 | Host port for cAdvisor |
| `HOLD_MINUTES` | 10 | How long unpaid seats stay reserved |
| `SEED_DEMO` | true | Create one demo event on first start |
| `LOG_LEVEL` | INFO | App log level |

Compose stops with an error if `DB_USER` or `DB_PASS` is missing (`${DB_USER:?...}`).

## Everyday commands

```sh
make up            # build + start + wait for healthy
make ps            # status and health of every container
make logs          # follow app + nginx logs
make test          # ruff + pytest against real Postgres (separate test DB)
make smoke         # end-to-end booking through nginx
make resilience    # persistence, scaling, DB outage
make scale         # 3 app replicas
make down          # stop, keep data
make clean         # stop and DELETE data
```

## Production hardening in this stack

| Practice | Where |
| -------- | ----- |
| Restart policy `unless-stopped` | every long-running service |
| Healthchecks + `depends_on: service_healthy` | db, app, nginx |
| Resource limits (CPU / memory) | `deploy.resources.limits` on db, app, nginx |
| Non-root user, read-only filesystem, `cap_drop: ALL`, `no-new-privileges` | app |
| Internal networks (no internet, no host access) | `backend`, `data` |
| Only nginx + cAdvisor publish ports | compose `ports:` |
| Log rotation (10 MB × 3 files) | `x-logging` |
| Rate limiting (20 r/s per IP, burst 40) | nginx |
| Secrets only in `.env` (git-ignored) + gitleaks in CI | `.gitignore`, `ci.yml` |
| Pinned image and package versions, Dependabot | Dockerfile, requirements, `.github/dependabot.yml` |

## Backup and restore

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
| `make up` hangs on app | `docker compose logs app` | DB credentials wrong in `.env`; `make clean` if you changed them after first start |
| `/health` returns 503 | `docker compose ps db` | `docker compose start db` — the app reconnects by itself |
| Port 80 already in use | `lsof -i :80` | set `HTTP_PORT=8000` in `.env` |
| 429 Too Many Requests | nginx rate limit | slow down, or raise `rate=` in `nginx/nginx.conf` |
| cAdvisor shows little data on macOS | Docker Desktop runs in a VM | expected; full metrics on Linux |

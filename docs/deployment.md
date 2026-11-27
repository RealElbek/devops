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
# backup
docker compose exec -T db pg_dump -U ticketing ticketing > backup-$(date +%F).sql
# restore (into a running, empty stack)
docker compose exec -T db psql -U ticketing ticketing < backup-2026-11-28.sql
```

## Troubleshooting

| Symptom | Check | Fix |
| ------- | ----- | --- |
| `make up` hangs on app | `docker compose logs app` | DB credentials wrong in `.env`; `make clean` if you changed them after first start |
| `/health` returns 503 | `docker compose ps db` | `docker compose start db` — the app reconnects by itself |
| Port 80 already in use | `lsof -i :80` | set `HTTP_PORT=8000` in `.env` |
| 429 Too Many Requests | nginx rate limit | slow down, or raise `rate=` in `nginx/nginx.conf` |
| cAdvisor shows little data on macOS | Docker Desktop runs in a VM | expected; full metrics on Linux |

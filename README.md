# Ticket Booking Platform — DevOps project

PDP University · Unit 4 DevOps · PayFast · Topic 1: **Chipta bron qilish**
(event, seat, booking, payment, ticket)

A REST API to sell event tickets **without ever selling the same seat twice**, packaged as a
production-like Docker stack: Nginx → Flask/Gunicorn (scalable) → PostgreSQL, monitored by cAdvisor,
tested in CI.

```
              :80                         backend (internal)              data (internal)
 customer ───► nginx ── load balance ───► app × N (Flask+Gunicorn) ─────► PostgreSQL ── pgdata volume
              rate limit, request id
 admin ──────► cAdvisor :8080  (CPU / memory / network of every container)
```

## Quick start

Requires Docker + Docker Compose v2.

```sh
git clone https://github.com/RealElbek/devops.git && cd devops
cp .env.example .env
docker compose up --build -d --wait      # or: make up
```

| URL | What |
| --- | ---- |
| <http://localhost> | API index |
| <http://localhost/api/v1/events> | Events (a demo event is created on first start) |
| <http://localhost/health> | Health (app + DB) |
| <http://localhost:8080> | cAdvisor monitoring |

Try a booking:

```sh
curl localhost/api/v1/events/1/seats
curl -X POST localhost/api/v1/bookings -H 'Content-Type: application/json' \
  -d '{"event_id":1,"seat_ids":[1,2],"customer_name":"Ali Valiyev","customer_email":"ali@example.com"}'
curl -X POST localhost/api/v1/bookings/1/pay -H 'Content-Type: application/json' -d '{"method":"click"}'
```

Stop: `make down` (keeps data) · Delete everything: `make clean` · All commands: `make help`

Backup: `make backup` · Restore: `make restore FILE=backups/<name>.dump` — details in [docs/deployment.md](docs/deployment.md#backup-and-restore)

## API

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET  | `/api/v1/events` | Events with available seat counts |
| POST | `/api/v1/events` | Create event + seat map (`rows`, `seats_per_row`, `price`) |
| GET  | `/api/v1/events/{id}/seats` | Seat map with availability |
| POST | `/api/v1/bookings` | Hold seats (pending, expires after `HOLD_MINUTES`) |
| GET  | `/api/v1/bookings/{id}` | Booking with seats, payment, tickets |
| POST | `/api/v1/bookings/{id}/pay` | Simulated payment → tickets issued |
| POST | `/api/v1/bookings/{id}/cancel` | Cancel and release seats |
| GET  | `/api/v1/tickets/{code}` | Check a ticket at the entrance |

Details and examples: [docs/api.md](docs/api.md)

## Testing

```sh
make test         # ruff lint + 17 pytest tests against real PostgreSQL (separate test DB)
make smoke        # full booking flow through nginx
make resilience   # data persistence, scaling to 3 replicas, database outage + recovery
```

CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs on every PR to `main`:
**secret scan (gitleaks) → lint + tests → full stack smoke + resilience**.
Latest results: [docs/report.md](docs/report.md)

## What makes it production-like

- **Healthchecks** on db, app, nginx + `depends_on: service_healthy` (correct startup order)
- **Restart policies**, **resource limits**, **log rotation**
- **Horizontal scaling**: `docker compose up -d --scale app=3`; nginx balances automatically
- **Self-healing**: if Postgres goes down, `/health` returns 503 and the app reconnects on its own
- **Persistence**: named volume `pgdata`
- **Security**: non-root, read-only container, `cap_drop: ALL`, internal networks, only nginx and
  cAdvisor publish ports, secrets in git-ignored `.env`, gitleaks in CI, no card data (simulated payments)
- **No double booking**: Postgres row locks + unique ticket per seat, tested with 20 parallel requests

## Project structure

```
app/
  ticketing/          Flask app: __init__.py (routes), service.py (business rules), db.py, schema.sql
  tests/              pytest integration tests
  Dockerfile          multi-stage: base → test → runtime (non-root, healthcheck)
nginx/nginx.conf      reverse proxy, load balancing, rate limit
docker-compose.yml    db, app, nginx, cadvisor (+ tests profile), 3 networks, 1 volume
scripts/              smoke_test.sh, resilience_test.sh
docs/                 architecture, api, deployment, decisions, report, team docs
.github/              CI, Dependabot, PR + issue templates, CODEOWNERS
Makefile              short commands
```

## Team & process

| Role | Document |
| ---- | -------- |
| Tech Lead | [access.md](docs/access.md) (collaborators, `main` protection), [CODEOWNERS](.github/CODEOWNERS) |
| Product Owner / Scrum | Issues + Project board, [meetings.md](docs/meetings.md) |
| QA & Code Review | [PR template](.github/pull_request_template.md), [review-checklist.md](docs/review-checklist.md), `app/tests/` |
| DevOps / Platform | [Dockerfile](app/Dockerfile), [docker-compose.yml](docker-compose.yml), [CI](.github/workflows/ci.yml), [deployment.md](docs/deployment.md) |
| Tech Writer & Security | this README, [decisions.md](docs/decisions.md), [access.md](docs/access.md), gitleaks |

Team agreement and roles: [docs/team-charter.md](docs/team-charter.md) ·
Architecture: [docs/architecture.md](docs/architecture.md)

## EP10 labs → where they are

| EP10 lab | In this project |
| -------- | --------------- |
| Lab 1: Reverse proxy | `nginx/nginx.conf`, app port not published |
| Lab 2: Health checks | `healthcheck:` on db / app / nginx, `docker compose ps` shows `(healthy)` |
| Lab 3: cAdvisor | `cadvisor` service on :8080, analysis in [docs/report.md](docs/report.md) |

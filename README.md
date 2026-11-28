# Ticket Booking Platform — DevOps project

PDP University · Unit 4 DevOps · PayFast · Topic 1: **Chipta bron qilish**
(event, seat, booking, payment, ticket)

A ticket booking platform that **never sells the same seat twice**, built as **4 microservices**
(each with its own database) behind an API gateway, packaged as a production-like Docker stack,
monitored by cAdvisor and tested in CI.

```
                    ┌──► event-service   ──► event-db     (events, seat maps)
 customer ─► :80    ├──► booking-service ──► booking-db   (seat holds, no double booking)
            gateway ┼──► payment-service ──► payment-db   (simulated payments)
            (nginx) └──► ticket-service  ──► ticket-db    (tickets, entrance check)
 admin ──► cAdvisor :8080  (CPU / memory / network of every container)
```

Each service has its own code, Dockerfile, tests, CI job and database, and can be scaled on its
own. Architecture and the reasons behind it: [docs/architecture.md](docs/architecture.md),
[docs/decisions.md](docs/decisions.md) (ADR-009 … ADR-012).

## Quick start

Requires Docker + Docker Compose v2.

```sh
git clone https://github.com/RealElbek/devops.git && cd devops
cp .env.example .env
docker compose up --build -d --wait      # or: make up
```

| URL | What |
| --- | ---- |
| <http://localhost> | **Dashboard**: live statistics + architecture with service health |
| <http://localhost/api> | Gateway index (list of services) |
| <http://localhost/api/v1/events> | Events (a demo event is created on first start) |
| <http://localhost/health/booking> | Health of one service + its DB (`event`, `booking`, `payment`, `ticket`) |
| <http://localhost:8080> | cAdvisor monitoring |

Try a booking:

```sh
curl localhost/api/v1/events/1/availability
curl -X POST localhost/api/v1/bookings -H 'Content-Type: application/json' \
  -d '{"event_id":1,"seat_ids":[1,2],"customer_name":"Ali Valiyev","customer_email":"ali@example.com"}'
curl -X POST localhost/api/v1/bookings/1/pay -H 'Content-Type: application/json' -d '{"method":"click"}'
```

Stop: `make down` (keeps data) · Delete everything: `make clean` · All commands: `make help`

Backup: `make backup` (all 4 databases → `backups/<timestamp>/`) · Restore: `make restore FILE=backups/<folder>` — details in [docs/deployment.md](docs/deployment.md#backup-and-restore)

Something broken? → [docs/runbook.md](docs/runbook.md) (symptom → check → fix for every common failure)

## API (all through the gateway)

| Method | Path | Service |
| ------ | ---- | ------- |
| GET / POST | `/api/v1/events` | event |
| GET  | `/api/v1/events/{id}/seats` | event |
| GET  | `/api/v1/events/{id}/availability` | booking |
| POST | `/api/v1/bookings` | booking |
| GET  | `/api/v1/bookings/{id}` | booking |
| POST | `/api/v1/bookings/{id}/cancel` | booking |
| POST | `/api/v1/bookings/{id}/pay` | payment |
| GET  | `/api/v1/payments/{booking_id}` | payment |
| GET  | `/api/v1/tickets/{code}` | ticket |

Details and examples: [docs/api.md](docs/api.md)

## Testing

```sh
make test         # per service: ruff lint + pytest against its own real PostgreSQL (32 tests)
make smoke        # full booking flow through the gateway: all 4 services together
make resilience   # persistence, scaling one service to 3 replicas, fault isolation
```

CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs on every PR to `main`:
**secret scan (gitleaks) → 4 service test jobs in parallel → full stack smoke + resilience**.
Latest results: [docs/report.md](docs/report.md)

## What makes it production-like

- **Microservices**: 4 independently built, tested and scalable services; API gateway in front
- **Database per service**: 4 Postgres containers, 4 volumes, separate credentials and networks
- **Fault isolation**: if booking-db goes down, events and tickets keep working; a down service
  returns a clean `503 "<service> unavailable"` instead of crashing callers (2 s / 5 s timeouts)
- **Safe payments across services**: every step is idempotent, so a failed `/pay` can be retried
  without charging twice or issuing duplicate tickets
- **Healthchecks** everywhere + `depends_on: service_healthy` (correct startup order)
- **Restart policies**, **resource limits**, **log rotation**, **request IDs** across all services
- **Horizontal scaling**: `docker compose up -d --scale booking-service=3`; the gateway balances automatically
- **Security**: non-root, read-only containers, `cap_drop: ALL`, internal networks, `/internal/*`
  endpoints not exposed, secrets in git-ignored `.env`, gitleaks in CI, no card data
- **No double booking**: advisory lock per seat + unique ticket per seat, tested with 20 parallel requests

## Project structure

```
services/
  common/             shared plumbing only: DB helpers, JSON errors, /health, HTTP client
  event-service/      events + seat maps          (event_service/, tests/, Dockerfile)
  booking-service/    seat holds, availability    (booking_service/, tests/, Dockerfile)
  payment-service/    simulated payments          (payment_service/, tests/, Dockerfile)
  ticket-service/     tickets, entrance check     (ticket_service/, tests/, Dockerfile)
nginx/nginx.conf      API gateway: routing per service, rate limit, request id
docker-compose.yml    4 services + 4 databases + gateway + cadvisor (+ tests profile)
scripts/              smoke_test.sh, resilience_test.sh, backup.sh, restore.sh, db_lib.sh
docs/                 architecture, api, deployment, decisions, report, team docs
.github/              CI, Dependabot, PR + issue templates, CODEOWNERS
Makefile              short commands
```

## Team & process

| Role | Document |
| ---- | -------- |
| Tech Lead | [access.md](docs/access.md) (collaborators, `main` protection), [CODEOWNERS](.github/CODEOWNERS) |
| Product Owner / Scrum | Issues + Project board, [meetings.md](docs/meetings.md) |
| QA & Code Review | [PR template](.github/pull_request_template.md), [review-checklist.md](docs/review-checklist.md), `services/*/tests/` |
| DevOps / Platform | [service Dockerfiles](services/), [docker-compose.yml](docker-compose.yml), [CI](.github/workflows/ci.yml), [deployment.md](docs/deployment.md), [runbook.md](docs/runbook.md) |
| Tech Writer & Security | this README, [decisions.md](docs/decisions.md), [access.md](docs/access.md), gitleaks |

Team agreement and roles: [docs/team-charter.md](docs/team-charter.md) ·
Architecture: [docs/architecture.md](docs/architecture.md)

## EP10 labs → where they are

| EP10 lab | In this project |
| -------- | --------------- |
| Lab 1: Reverse proxy | `nginx/nginx.conf` (API gateway), service ports not published |
| Lab 2: Health checks | `healthcheck:` on every DB, service and the gateway, `docker compose ps` shows `(healthy)` |
| Lab 3: cAdvisor | `cadvisor` service on :8080, analysis in [docs/report.md](docs/report.md) |

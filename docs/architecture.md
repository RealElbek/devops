# Architecture

## Overview

```mermaid
flowchart LR
    user[Customer / curl] -->|HTTP :80| nginx[nginx<br/>reverse proxy, rate limit]
    nginx -->|backend network| app1[app replica 1]
    nginx -->|backend network| app2[app replica N]
    app1 -->|data network| db[(PostgreSQL 16)]
    app2 -->|data network| db
    db --- vol[(pgdata volume)]
    admin[Admin] -->|:8080| cadvisor[cAdvisor<br/>container metrics]
```

| Container  | Image                       | Networks           | Published port | Purpose |
| ---------- | --------------------------- | ------------------ | -------------- | ------- |
| `nginx`    | `nginx:1.27-alpine`         | frontend, backend  | 80             | Single entry point, load balancing, rate limiting, `X-Request-ID` |
| `app`      | built from `app/Dockerfile` | backend, data      | — (only 5000 inside) | Flask + Gunicorn REST API, can run N replicas |
| `db`       | `postgres:16-alpine`        | data               | —              | All data, stored in the `pgdata` named volume |
| `cadvisor` | `gcr.io/cadvisor/cadvisor`  | frontend           | 8080           | CPU / memory / network / disk per container |
| `tests`    | `app/Dockerfile` (test stage) | data             | —              | Only with `--profile test`: ruff + pytest on a separate `ticketing_test` DB |

### Networks (isolation)

- `frontend` — normal bridge network. Only nginx and cAdvisor are here.
- `backend` — `internal: true`. nginx ↔ app. No internet, not reachable from the host.
- `data` — `internal: true`. app ↔ db. nginx cannot even see the database.

## Domain model

```mermaid
erDiagram
    EVENTS ||--o{ SEATS : has
    EVENTS ||--o{ BOOKINGS : has
    BOOKINGS ||--|{ BOOKING_SEATS : holds
    SEATS ||--o{ BOOKING_SEATS : "held by"
    BOOKINGS ||--o| PAYMENTS : "paid by"
    BOOKINGS ||--o{ TICKETS : issues
    SEATS ||--o| TICKETS : "sold as"
```

## Booking lifecycle

```mermaid
stateDiagram-v2
    [*] --> pending: POST /bookings (seats held for HOLD_MINUTES)
    pending --> paid: POST /bookings/{id}/pay -> tickets issued
    pending --> cancelled: POST /bookings/{id}/cancel
    pending --> expired: hold time passed, seats released
    paid --> [*]
```

## How double booking is prevented

1. `POST /bookings` locks the requested seat rows with `SELECT ... FOR UPDATE`. If two customers
   click the same seat at the same moment, the second request waits for the first transaction,
   then sees the seat as taken and gets `409 Conflict`.
2. `tickets.seat_id` is `UNIQUE` in the database: even a bug in the code cannot sell one seat twice.
3. Tested by `test_concurrent_bookings_only_one_wins`: 20 parallel requests → exactly 1 success.

## Startup order and health

`db` (healthy: `pg_isready`) → `app` (healthy: `/health` runs `SELECT 1`) → `nginx` (healthy:
`/nginx-health`). `depends_on: condition: service_healthy` makes each service wait for the previous
one to be **ready**, not just started. The app also retries the DB connection on startup and creates
its schema under a Postgres advisory lock, so several replicas can start at the same time safely.

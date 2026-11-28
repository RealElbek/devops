# Architecture decisions (ADR)

Short records of *why* things are the way they are. New decision → new section, never edit old ones
(write a new one that replaces it).

## ADR-001: Topic — ticket booking
**Date:** 2026-11-28 · **Status:** accepted
Chosen from the 6 course topics: *Chipta bron qilish (event, seat, booking, payment, ticket)*.
It has a clear flow and one hard, testable problem (no double booking), which is good for showing
DevOps practices without a huge codebase.

## ADR-002: One service (modular monolith), not microservices
**Date:** 2026-11-28 · **Status:** replaced by ADR-009
The team is small. One Flask service with one Postgres database is easier to run, test and explain.
Code is split by responsibility (`db.py`, `service.py`, routes in `__init__.py`), so it can be split
into services later if needed. Scaling is done horizontally with replicas behind nginx.

## ADR-003: PostgreSQL row locks to prevent double booking
**Date:** 2026-11-28 · **Status:** replaced by ADR-011
`SELECT ... FOR UPDATE` on seat rows + `UNIQUE (seat_id)` on tickets. Simpler and safer than
application-level locks or Redis, and it works with any number of app replicas because the lock
lives in the database.

## ADR-004: Simulated payments
**Date:** 2026-11-28 · **Status:** accepted
The `/pay` endpoint only accepts a method name (`card`, `click`, `payme`, `cash`) and always
succeeds. We never accept or store card numbers — handling real card data needs PCI DSS
compliance. A real provider (Click / Payme) would be integrated through their API later.

## ADR-005: nginx as the only entry point
**Date:** 2026-11-28 · **Status:** accepted
The app port is not published. nginx gives us load balancing across replicas, rate limiting,
request IDs and one place to add TLS later. It re-resolves Docker DNS every 5 s, so scaling the app
does not require restarting nginx.

## ADR-006: Gunicorn instead of the Flask dev server
**Date:** 2026-11-28 · **Status:** accepted
Flask's built-in server is single-process and meant for development. Gunicorn runs 2 workers ×
4 threads per container.

## ADR-007: Tests against real PostgreSQL
**Date:** 2026-11-28 · **Status:** accepted
Locking behaviour (ADR-003) cannot be tested with SQLite or mocks. Tests run in a container next to
the real `db` service, on a separate `ticketing_test` database, both locally (`make test`) and in CI.

## ADR-008: cAdvisor for monitoring
**Date:** 2026-11-28 · **Status:** accepted
Zero configuration, shows CPU / memory / network per container. Next step: Prometheus + Grafana
reading cAdvisor's `/metrics`.

## ADR-009: Microservices instead of a monolith
**Date:** 2026-11-28 · **Status:** accepted · replaces ADR-002
The course requires a microservice architecture. The app is split along the business flow into
4 services: **event** (catalog), **booking** (seat holds), **payment**, **ticket**. Each has its own
code, Dockerfile, image, tests, CI job and database, and can be deployed and scaled on its own
(`docker compose up --scale booking-service=3`). An nginx **API gateway** is the single entry point
and routes by URL. Services talk over HTTP/JSON with short timeouts; a down service gives a clean
503 instead of breaking the others. A tiny shared `common` library (DB helpers, errors, HTTP client)
avoids copy-pasting plumbing; it holds no business logic.

## ADR-010: Database per service
**Date:** 2026-11-28 · **Status:** accepted
Each service has its own Postgres container, volume, credentials and internal network. No service
can read another service's tables (it cannot even reach the other database). Data from another
service is referenced by id and, where needed, copied at the time of the action (seat label/price
in a booking, event title/venue in a ticket). Cost: 4 Postgres containers (~20 MiB each idle).

## ADR-011: Advisory lock per seat to prevent double booking
**Date:** 2026-11-28 · **Status:** accepted · replaces ADR-003
Seat rows now live in event-db, so booking-service cannot `SELECT ... FOR UPDATE` them. Instead it
takes `pg_advisory_xact_lock(7, seat_id)` in booking-db for each requested seat (sorted, so no
deadlocks), then checks for active holds. Works across booking-service replicas because the lock
is in the database. `UNIQUE (seat_id)` in ticket-db stays as the last safety net.

## ADR-012: Idempotent steps instead of a distributed transaction for payments
**Date:** 2026-11-28 · **Status:** accepted
Paying touches payment-, booking- and ticket-service. Instead of a distributed transaction
(complex, needs a coordinator), each step is idempotent: `mark-paid` and ticket issuing can be
called twice safely, and the payment row is locked and records its status. If any service fails
in the middle, the client retries `/pay` and the flow continues without charging or issuing twice.
A message queue (e.g. RabbitMQ) with an outbox would be the next step for automatic retries.

## ADR-013: One backup folder for all 4 databases; each database restored in its own transaction
**Date:** 2026-11-28 · **Status:** accepted
With a database per service (ADR-010), a backup is one folder `backups/<timestamp>/` holding
`events.dump`, `bookings.dump`, `payments.dump`, `tickets.dump` (`pg_dump -Fc`), so the 4 dumps are
always restored together. Every dump is checked with `pg_restore --list`, and the folder only gets
its real name when all 4 are good. Restore checks all 4 files first, takes a safety backup, stops the
4 services, then restores each database with `--single-transaction`. The 4 databases are separate
Postgres servers, so the 4 restores together are **not** atomic: if one fails, the earlier ones are
already restored. We accept this instead of a distributed transaction (too complex for this size)
because the script stops, lists what was restored, and the safety backup brings everything back
(tested). The dumps are also not taken at the exact same instant; for consistency, take backups when
traffic is low (nightly cron). See [deployment.md](deployment.md#backup-and-restore) and
[runbook.md §5–6](runbook.md#5-data-was-deleted-or-corrupted).

# Architecture decisions (ADR)

Short records of *why* things are the way they are. New decision → new section, never edit old ones
(write a new one that replaces it).

## ADR-001: Topic — ticket booking
**Date:** 2026-11-28 · **Status:** accepted
Chosen from the 6 course topics: *Chipta bron qilish (event, seat, booking, payment, ticket)*.
It has a clear flow and one hard, testable problem (no double booking), which is good for showing
DevOps practices without a huge codebase.

## ADR-002: One service (modular monolith), not microservices
**Date:** 2026-11-28 · **Status:** accepted
The team is small. One Flask service with one Postgres database is easier to run, test and explain.
Code is split by responsibility (`db.py`, `service.py`, routes in `__init__.py`), so it can be split
into services later if needed. Scaling is done horizontally with replicas behind nginx.

## ADR-003: PostgreSQL row locks to prevent double booking
**Date:** 2026-11-28 · **Status:** accepted
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

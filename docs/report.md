# Test report

Results from running the microservices stack locally on 2026-11-28 (macOS, Docker Desktop). CI runs
the same checks on every PR.

## 1. Lint + tests — `make test`

Each service is linted and tested on its own, against its own real PostgreSQL (separate `*_test`
database). Other services are replaced by in-memory fakes, so failures can be simulated.

```
=== event-service ===    All checks passed! (ruff)   7 passed
=== booking-service ===  All checks passed! (ruff)  10 passed
=== payment-service ===  All checks passed! (ruff)   8 passed
=== ticket-service ===   All checks passed! (ruff)   7 passed
```

Highlights:
- `test_concurrent_bookings_only_one_wins` (booking): 20 parallel requests for one seat → exactly
  1 × 201, 19 × 409.
- `test_ticket_service_down_then_retry_finishes_payment` (payment): ticket-service fails after the
  payment, a retry issues the tickets without a second charge.
- `test_booking_service_down_records_nothing` (payment): nothing is saved, retry works.
- `test_same_seat_can_never_get_two_tickets` (ticket): the database refuses a second ticket.
- `test_demo_seed_runs_once_even_in_parallel` (event): 8 parallel starts → demo event created once.

## 2. Health — `docker compose ps`

```
ticketing-booking-db-1        Up (healthy)
ticketing-booking-service-1   Up (healthy)
ticketing-cadvisor-1          Up (healthy)
ticketing-event-db-1          Up (healthy)
ticketing-event-service-1     Up (healthy)
ticketing-gateway-1           Up (healthy)
ticketing-payment-db-1        Up (healthy)
ticketing-payment-service-1   Up (healthy)
ticketing-ticket-db-1         Up (healthy)
ticketing-ticket-service-1    Up (healthy)
```

## 3. Smoke test — `make smoke` (all services together)

```
PASS  GET /health/event -> ok          (same for booking, payment, ticket)
PASS  [event-service]   POST /events -> event 2 with 8 seats
PASS  [booking-service] GET /events/2/availability -> picked seats 51 52
PASS  [booking-service] POST /bookings -> booking 1 pending, total 100000 UZS
PASS  [booking-service] same seat again -> 409 (no double booking)
PASS  [payment-service] POST /bookings/1/pay -> payment succeeded
PASS  [ticket-service]  tickets issued: TKT-2CC4-4584, TKT-46F8-8EB4
PASS  [booking-service] booking 1 is now paid
PASS  [payment-service] pay again -> 409 (no double charge)
PASS  [ticket-service]  GET /tickets/TKT-2CC4-4584 -> valid
PASS  [gateway]         /internal/* is not reachable from outside
```

## 4. Resilience — `make resilience`

```
1) Persistence:      events before=2 after=2   (docker compose down + up)
2) Scaling:          3 booking-service replicas, 30 requests served by 3 different replicas
3) booking-db down:  /health/booking 503, event-service and ticket-service still OK,
                     booking-service did not crash; booking-db back -> recovered by itself
4) event-service down: POST /bookings -> clean 503, payment-service still OK; back -> API works
```

Network isolation, checked from inside event-service: `event-db` reachable; `booking-db`,
`payment-db`, `ticket-db` **not reachable**.

## 5. Monitoring — cAdvisor / `docker stats`

| Container | Memory / limit | Comment |
| --------- | -------------- | ------- |
| booking-service | 75 MiB / 256 MiB | busiest service: availability + locking |
| payment-service | 74 MiB / 256 MiB | |
| ticket-service  | 75 MiB / 256 MiB | |
| event-service   | 58 MiB / 256 MiB | |
| each `*-db`     | 20–22 MiB / 256 MiB | 4 databases ≈ 85 MiB total |
| gateway         | 11 MiB / 128 MiB | very light |
| cadvisor        | 31 MiB | monitoring overhead is small |

Image sizes: each service 203 MB (python:3.12-slim + deps) · nginx 75 MB · cadvisor 115 MB ·
postgres 420 MB (shared by all 4 databases: same image, pulled once).

**Conclusion:** the whole stack uses ≈ 450 MiB of RAM. Microservices cost more memory than the old
single service (~120 MiB), but each part scales and fails on its own: booking-service, which does the
most work, can be scaled to 3 replicas without touching the others. Next steps: a connection pooler
(PgBouncer) per database, and Prometheus + Grafana reading cAdvisor's `/metrics`.

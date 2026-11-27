# Test report

Results from running the stack locally on 2026-11-28 (macOS, Docker Desktop). CI runs the same
checks on every PR.

## 1. Lint + tests — `make test`

```
All checks passed!                       (ruff)
17 passed in 2.7s                        (pytest, real PostgreSQL 16)
```

Highlights:
- `test_concurrent_bookings_only_one_wins` — 20 parallel requests for one seat → exactly 1 × 201, 19 × 409.
- `test_expired_hold_releases_seat` — an unpaid hold expires and the seat becomes free again.
- `test_demo_seed_runs_once_even_in_parallel` — 8 parallel starts create the demo event only once
  (this test was added after a real race condition was found: 2 Gunicorn workers both seeded).

## 2. Health — `docker compose ps`

```
ticketing-app-1        Up (healthy)
ticketing-cadvisor-1   Up (healthy)
ticketing-db-1         Up (healthy)
ticketing-nginx-1      Up (healthy)
```

## 3. Smoke test — `make smoke`

```
PASS  GET /health -> ok
PASS  POST /events -> event 2 with 8 seats
PASS  GET /events/2/seats -> picked seats 51 52
PASS  POST /bookings -> booking 1 pending, total 100000 UZS
PASS  same seat again -> 409 (no double booking)
PASS  POST /bookings/1/pay -> paid
PASS  tickets issued: TKT-1EA2-047B, TKT-0F52-0590
PASS  GET /tickets/TKT-1EA2-047B -> valid
```

## 4. Resilience — `make resilience`

```
1) Persistence:  events before=2 after=2   (docker compose down + up)
2) Scaling:      3 app replicas, 30 requests served by 3 different replicas
3) DB outage:    db stopped -> /health 503, app kept running,
                 db started -> /health 200 again, API works (no manual restart)
```

## 5. Monitoring — cAdvisor / `docker stats`

| Container | CPU | Memory / limit | Comment |
| --------- | --- | -------------- | ------- |
| app       | spikes during requests | 62 MiB / 256 MiB | heaviest: Python + 2 workers × 4 threads |
| db        | < 1 % idle | 21 MiB / 512 MiB | grows with data and connections |
| nginx     | ~0 %  | 12 MiB / 128 MiB | very light |
| cadvisor  | < 1 % | 21 MiB | monitoring overhead is small |

Image sizes: app 198 MB · nginx 75 MB · cadvisor 115 MB · postgres 420 MB.

**Conclusion:** the app container is the first bottleneck. It scales horizontally
(`docker compose up --scale app=3`) because state lives in Postgres and seat locking happens in the
database. The next bottleneck would be Postgres connections → add a connection pooler (PgBouncer).

# API

Base URL: `http://localhost` (through nginx). All bodies are JSON. Prices are integers in UZS.

| Method | Path | Description | Success | Errors |
| ------ | ---- | ----------- | ------- | ------ |
| GET  | `/health` | App + DB status, `served_by` = replica hostname | 200 | 503 if DB is down |
| GET  | `/api/v1/events` | List events with `total_seats` / `available_seats` | 200 | |
| POST | `/api/v1/events` | Create event + seat map | 201 | 400 |
| GET  | `/api/v1/events/{id}` | One event | 200 | 404 |
| GET  | `/api/v1/events/{id}/seats` | Seats with `available` flag | 200 | 404 |
| POST | `/api/v1/bookings` | Hold seats for a customer | 201 | 400, 404, 409 seat taken |
| GET  | `/api/v1/bookings/{id}` | Booking with seats, payment, tickets | 200 | 404 |
| POST | `/api/v1/bookings/{id}/pay` | Pay → status `paid`, tickets issued | 200 | 400, 404, 409 |
| POST | `/api/v1/bookings/{id}/cancel` | Cancel a pending booking | 200 | 404, 409 |
| GET  | `/api/v1/tickets/{code}` | Check a ticket at the entrance | 200 | 404 |

Errors always look like `{"error": "seats already taken: A1"}`.

## Walkthrough with curl

```sh
# 1. Events
curl localhost/api/v1/events

# 2. Create an event: 3 rows x 8 seats, 120 000 UZS each
curl -X POST localhost/api/v1/events -H 'Content-Type: application/json' -d '{
  "title": "Stand-up Night", "venue": "Tashkent, Turkiston Palace",
  "starts_at": "2026-12-25T20:00:00+05:00", "rows": 3, "seats_per_row": 8, "price": 120000}'

# 3. Seat map
curl localhost/api/v1/events/1/seats

# 4. Book seats 1 and 2 (held for HOLD_MINUTES, default 10)
curl -X POST localhost/api/v1/bookings -H 'Content-Type: application/json' -d '{
  "event_id": 1, "seat_ids": [1, 2], "customer_name": "Ali Valiyev", "customer_email": "ali@example.com"}'

# 5. Pay (simulated provider: card | click | payme | cash)
curl -X POST localhost/api/v1/bookings/1/pay -H 'Content-Type: application/json' -d '{"method": "click"}'

# 6. Check a ticket
curl localhost/api/v1/tickets/TKT-1A2B-3C4D
```

## Rules

- Max 10 seats per booking; seats must belong to the event; no duplicates.
- A seat is **taken** if it is in a `paid` booking or a `pending` booking that has not expired.
- Only `pending` bookings can be paid or cancelled. Paying twice → `409`.
- Payment is **simulated**: the API never accepts or stores card numbers (see decisions.md, ADR-004).

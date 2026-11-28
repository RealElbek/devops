# API

Base URL: `http://localhost` (the gateway). All bodies are JSON. Prices are integers in UZS.
The **Service** column says which microservice answers; you always call the gateway.

| Method | Path | Service | Description | Success | Errors |
| ------ | ---- | ------- | ----------- | ------- | ------ |
| GET  | `/health/{event\|booking\|payment\|ticket}` | that one | Service + its DB status, `served_by` = replica | 200 | 503 if its DB is down |
| GET  | `/api/v1/events` | event | List events with `total_seats` | 200 | |
| POST | `/api/v1/events` | event | Create event + seat map | 201 | 400 |
| GET  | `/api/v1/events/{id}` | event | One event | 200 | 404 |
| GET  | `/api/v1/events/{id}/seats` | event | Seat catalog (label, price) | 200 | 404 |
| GET  | `/api/v1/events/{id}/availability` | booking | Seats with `available` flag + counts | 200 | 404, 503 |
| POST | `/api/v1/bookings` | booking | Hold seats for a customer | 201 | 400, 404, 409 seat taken, 503 |
| GET  | `/api/v1/bookings/{id}` | booking | Booking with its seats and status | 200 | 404 |
| POST | `/api/v1/bookings/{id}/cancel` | booking | Cancel a pending booking | 200 | 404, 409 |
| POST | `/api/v1/bookings/{id}/pay` | payment | Pay → booking `paid`, tickets issued | 200 | 400, 404, 409, 503 |
| GET  | `/api/v1/payments/{booking_id}` | payment | Payment of a booking | 200 | 404 |
| GET  | `/api/v1/tickets/{code}` | ticket | Check a ticket at the entrance | 200 | 404 |
| GET  | `/api/v1/tickets?booking_id={id}` | ticket | Tickets of a booking | 200 | 400 |

Errors always look like `{"error": "seats already taken: A1"}`. `503 {"error": "event-service
unavailable"}` means a service the request needs is down; the rest of the system keeps working.

## Internal endpoints (not reachable through the gateway)

| Method | Path | Service | Called by |
| ------ | ---- | ------- | --------- |
| POST | `/internal/seats/lookup` | event | booking-service |
| POST | `/internal/bookings/{id}/mark-paid` | booking | payment-service (idempotent) |
| POST | `/internal/tickets` | ticket | payment-service (idempotent: `{"created": false}` on repeat) |

## Walkthrough with curl

```sh
# 1. Events
curl localhost/api/v1/events

# 2. Create an event: 3 rows x 8 seats, 120 000 UZS each
curl -X POST localhost/api/v1/events -H 'Content-Type: application/json' -d '{
  "title": "Stand-up Night", "venue": "Tashkent, Turkiston Palace",
  "starts_at": "2026-12-25T20:00:00+05:00", "rows": 3, "seats_per_row": 8, "price": 120000}'

# 3. Which seats are free
curl localhost/api/v1/events/1/availability

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
- Only `pending` bookings can be paid or cancelled. Paying twice → `409`, never a second charge.
- If `/pay` returns 503, it is safe to call it again: it continues where it stopped.
- Payment is **simulated**: the API never accepts or stores card numbers (see decisions.md, ADR-004).

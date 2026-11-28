#!/usr/bin/env bash
# Full happy path through the gateway, so all 4 services work TOGETHER:
#   event-service -> booking-service -> payment-service -> ticket-service
# Usage: ./scripts/smoke_test.sh [BASE_URL]
set -euo pipefail
BASE="${1:-http://localhost}"
API="$BASE/api/v1"
pass() { echo "  PASS  $*"; }
fail() { echo "  FAIL  $*"; exit 1; }
json() { python3 -c "import sys,json; d=json.load(sys.stdin); print($1)"; }
status() { curl -s -o /dev/null -w '%{http_code}' "$@"; }

echo "Smoke test against $BASE"

for svc in event booking payment ticket; do
  curl -fsS "$BASE/health/$svc" | grep -q '"status":"ok"' && pass "GET /health/$svc -> ok" || fail "$svc-service health"
done

event_id=$(curl -fsS -X POST "$API/events" -H 'Content-Type: application/json' -d '{
  "title":"Smoke Test Show","venue":"CI Hall","starts_at":"2026-12-31T19:00:00+05:00",
  "rows":2,"seats_per_row":4,"price":50000}' | json 'd["id"]')
pass "[event-service]   POST /events -> event $event_id with 8 seats"

read -r s1 s2 < <(curl -fsS "$API/events/$event_id/availability" | json '" ".join(str(s["id"]) for s in d["seats"] if s["available"])' | cut -d' ' -f1,2)
pass "[booking-service] GET /events/$event_id/availability -> picked seats $s1 $s2"

booking=$(curl -fsS -X POST "$API/bookings" -H 'Content-Type: application/json' \
  -d "{\"event_id\":$event_id,\"seat_ids\":[$s1,$s2],\"customer_name\":\"Smoke Test\",\"customer_email\":\"smoke@example.com\"}")
booking_id=$(echo "$booking" | json 'd["id"]')
[ "$(echo "$booking" | json 'd["status"]')" = pending ] && pass "[booking-service] POST /bookings -> booking $booking_id pending, total $(echo "$booking" | json 'd["total"]') UZS" || fail "booking"

code=$(status -X POST "$API/bookings" -H 'Content-Type: application/json' \
  -d "{\"event_id\":$event_id,\"seat_ids\":[$s1],\"customer_name\":\"Other\",\"customer_email\":\"other@example.com\"}")
[ "$code" = 409 ] && pass "[booking-service] same seat again -> 409 (no double booking)" || fail "double booking returned $code"

paid=$(curl -fsS -X POST "$API/bookings/$booking_id/pay" -H 'Content-Type: application/json' -d '{"method":"card"}')
[ "$(echo "$paid" | json 'd["payment"]["status"]')" = succeeded ] && pass "[payment-service] POST /bookings/$booking_id/pay -> payment succeeded" || fail "payment"
ticket=$(echo "$paid" | json 'd["tickets"][0]["code"]')
pass "[ticket-service]  tickets issued: $(echo "$paid" | json '", ".join(t["code"] for t in d["tickets"])')"

[ "$(curl -fsS "$API/bookings/$booking_id" | json 'd["status"]')" = paid ] && pass "[booking-service] booking $booking_id is now paid" || fail "booking not marked paid"

code=$(status -X POST "$API/bookings/$booking_id/pay" -H 'Content-Type: application/json' -d '{"method":"card"}')
[ "$code" = 409 ] && pass "[payment-service] pay again -> 409 (no double charge)" || fail "second payment returned $code"

curl -fsS "$API/tickets/$ticket" | grep -q '"event":"Smoke Test Show"' && pass "[ticket-service]  GET /tickets/$ticket -> valid" || fail "ticket lookup"

code=$(status -X POST "$BASE/internal/bookings/$booking_id/mark-paid")
[ "$code" = 404 ] && pass "[gateway]         /internal/* is not reachable from outside" || fail "internal endpoint exposed ($code)"

curl -fsS "$BASE/" | grep -q '<title>Ticket Booking Platform</title>' && pass "[gateway]         GET / -> dashboard page" || fail "dashboard page"
for svc in event booking payment ticket; do
  curl -fsS "$API/stats/$svc" | python3 -c "import sys,json; json.load(sys.stdin)" || fail "stats/$svc"
done
sold=$(curl -fsS "$API/stats/booking" | json 'd["seats_sold"]')
[ "$sold" -ge 2 ] && pass "[dashboard]       GET /api/v1/stats/* from all 4 services ($sold seats sold)" || fail "stats: seats_sold=$sold"

echo "Smoke test passed."

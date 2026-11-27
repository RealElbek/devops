#!/usr/bin/env bash
# Full happy path through Nginx: event -> seats -> booking -> payment -> ticket.
# Usage: ./scripts/smoke_test.sh [BASE_URL]
set -euo pipefail
BASE="${1:-http://localhost}"
API="$BASE/api/v1"
pass() { echo "  PASS  $*"; }
fail() { echo "  FAIL  $*"; exit 1; }
json() { python3 -c "import sys,json; d=json.load(sys.stdin); print($1)"; }

echo "Smoke test against $BASE"

curl -fsS "$BASE/health" | grep -q '"status":"ok"' && pass "GET /health -> ok" || fail "health"

event_id=$(curl -fsS -X POST "$API/events" -H 'Content-Type: application/json' -d '{
  "title":"Smoke Test Show","venue":"CI Hall","starts_at":"2026-12-31T19:00:00+05:00",
  "rows":2,"seats_per_row":4,"price":50000}' | json 'd["id"]')
pass "POST /events -> event $event_id with 8 seats"

read -r s1 s2 < <(curl -fsS "$API/events/$event_id/seats" | json '" ".join(str(s["id"]) for s in d if s["available"])' | cut -d' ' -f1,2)
pass "GET /events/$event_id/seats -> picked seats $s1 $s2"

booking=$(curl -fsS -X POST "$API/bookings" -H 'Content-Type: application/json' \
  -d "{\"event_id\":$event_id,\"seat_ids\":[$s1,$s2],\"customer_name\":\"Smoke Test\",\"customer_email\":\"smoke@example.com\"}")
booking_id=$(echo "$booking" | json 'd["id"]')
[ "$(echo "$booking" | json 'd["status"]')" = pending ] && pass "POST /bookings -> booking $booking_id pending, total $(echo "$booking" | json 'd["total"]') UZS" || fail "booking"

code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API/bookings" -H 'Content-Type: application/json' \
  -d "{\"event_id\":$event_id,\"seat_ids\":[$s1],\"customer_name\":\"Other\",\"customer_email\":\"other@example.com\"}")
[ "$code" = 409 ] && pass "same seat again -> 409 (no double booking)" || fail "double booking returned $code"

paid=$(curl -fsS -X POST "$API/bookings/$booking_id/pay" -H 'Content-Type: application/json' -d '{"method":"card"}')
[ "$(echo "$paid" | json 'd["status"]')" = paid ] && pass "POST /bookings/$booking_id/pay -> paid" || fail "payment"
ticket=$(echo "$paid" | json 'd["tickets"][0]["code"]')
pass "tickets issued: $(echo "$paid" | json '", ".join(t["code"] for t in d["tickets"])')"

curl -fsS "$API/tickets/$ticket" | grep -q '"event":"Smoke Test Show"' && pass "GET /tickets/$ticket -> valid" || fail "ticket lookup"

echo "Smoke test passed."

#!/usr/bin/env bash
# Production checks: data persistence, scaling one service, and fault isolation
# (one service's database going down must not break the other services).
# Usage: ./scripts/resilience_test.sh [BASE_URL]      (run from the repo root, stack must be up)
set -euo pipefail
BASE="${1:-http://localhost}"
pass() { echo "  PASS  $*"; }
fail() { echo "  FAIL  $*"; docker compose ps; exit 1; }
json() { python3 -c "import sys,json; d=json.load(sys.stdin); print($1)"; }
status() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
wait_for() {  # wait_for <expected http code> <url> <seconds>
  for _ in $(seq 1 "$3"); do
    [ "$(status "$2")" = "$1" ] && return 0
    sleep 1
  done
  return 1
}

echo "1) Persistence: data survives 'docker compose down' + 'up'"
before=$(curl -fsS "$BASE/api/v1/events" | json 'len(d)')
docker compose down >/dev/null 2>&1
docker compose up -d --wait --wait-timeout 180 >/dev/null 2>&1
after=$(curl -fsS "$BASE/api/v1/events" | json 'len(d)')
[ "$before" = "$after" ] && pass "events before=$before after=$after" || fail "lost data: before=$before after=$after"

echo "2) Scaling: 3 booking-service replicas behind the gateway (other services stay at 1)"
docker compose up -d --scale booking-service=3 --no-recreate --wait --wait-timeout 180 >/dev/null 2>&1
running=$(docker compose ps booking-service --status running -q | wc -l | tr -d ' ')
[ "$running" = 3 ] && pass "3 booking-service containers running" || fail "expected 3 replicas, got $running"
sleep 6   # the gateway re-resolves service names every 5s
hosts=$(for _ in $(seq 1 30); do curl -fsS "$BASE/health/booking" | json 'd["served_by"]'; done | sort -u | wc -l | tr -d ' ')
[ "$hosts" -ge 2 ] && pass "30 requests were served by $hosts different replicas" || fail "load not balanced ($hosts replica)"
docker compose up -d --scale booking-service=1 --wait --wait-timeout 180 >/dev/null 2>&1
pass "scaled back to 1 replica"

echo "3) Fault isolation: booking-db goes down"
docker compose stop booking-db >/dev/null 2>&1
wait_for 503 "$BASE/health/booking" 20 && pass "booking-db stopped -> /health/booking returns 503" || fail "health did not report the outage"
[ "$(status "$BASE/api/v1/events")" = 200 ] && pass "event-service still works (GET /events -> 200)" || fail "event-service broken by booking-db outage"
[ "$(status "$BASE/health/ticket")" = 200 ] && pass "ticket-service still healthy" || fail "ticket-service broken by booking-db outage"
[ "$(docker compose ps booking-service --status running -q | wc -l | tr -d ' ')" -ge 1 ] && pass "booking-service kept running (no crash)" || fail "booking-service crashed"
docker compose start booking-db >/dev/null 2>&1
wait_for 200 "$BASE/health/booking" 60 && pass "booking-db started -> /health/booking back to 200 (auto-recovered)" || fail "booking-service did not recover"

echo "4) Fault isolation: event-service goes down"
docker compose stop event-service >/dev/null 2>&1
code=$(status -X POST "$BASE/api/v1/bookings" -H 'Content-Type: application/json' \
  -d '{"event_id":1,"seat_ids":[1],"customer_name":"X","customer_email":"x@example.com"}')
[ "$code" = 503 ] && pass "booking while event-service is down -> clean 503, not a crash" || fail "expected 503, got $code"
[ "$(status "$BASE/health/payment")" = 200 ] && pass "payment-service still healthy" || fail "payment-service broken"
docker compose start event-service >/dev/null 2>&1
docker compose up -d --wait --wait-timeout 180 >/dev/null 2>&1
wait_for 200 "$BASE/api/v1/events" 60 && pass "event-service started -> API works again" || fail "API broken after outage"

echo "Resilience test passed."

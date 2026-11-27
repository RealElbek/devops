#!/usr/bin/env bash
# Production checks: data persistence, horizontal scaling, database outage recovery.
# Usage: ./scripts/resilience_test.sh [BASE_URL]      (run from the repo root, stack must be up)
set -euo pipefail
BASE="${1:-http://localhost}"
pass() { echo "  PASS  $*"; }
fail() { echo "  FAIL  $*"; docker compose ps; exit 1; }
json() { python3 -c "import sys,json; d=json.load(sys.stdin); print($1)"; }
wait_for() {  # wait_for <expected http code> <url> <seconds>
  for _ in $(seq 1 "$3"); do
    [ "$(curl -s -o /dev/null -w '%{http_code}' "$2")" = "$1" ] && return 0
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

echo "2) Scaling: 3 app replicas behind nginx"
docker compose up -d --scale app=3 --no-recreate --wait --wait-timeout 180 >/dev/null 2>&1
running=$(docker compose ps app --status running -q | wc -l | tr -d ' ')
[ "$running" = 3 ] && pass "3 app containers running" || fail "expected 3 replicas, got $running"
sleep 6   # nginx re-resolves the 'app' DNS name every 5s
hosts=$(for _ in $(seq 1 30); do curl -fsS "$BASE/health" | json 'd["served_by"]'; done | sort -u | wc -l | tr -d ' ')
[ "$hosts" -ge 2 ] && pass "30 requests were served by $hosts different replicas" || fail "load not balanced ($hosts replica)"
docker compose up -d --scale app=1 --wait --wait-timeout 180 >/dev/null 2>&1
pass "scaled back to 1 replica"

echo "3) Database outage: app reports the problem and recovers by itself"
docker compose stop db >/dev/null 2>&1
wait_for 503 "$BASE/health" 20 && pass "db stopped -> /health returns 503" || fail "health did not report db outage"
[ "$(docker compose ps app --status running -q | wc -l | tr -d ' ')" -ge 1 ] && pass "app container kept running (no crash)" || fail "app crashed"
docker compose start db >/dev/null 2>&1
wait_for 200 "$BASE/health" 60 && pass "db started -> /health back to 200 (auto-recovered)" || fail "app did not recover"
curl -fsS "$BASE/api/v1/events" >/dev/null && pass "API works again after outage" || fail "API broken after outage"

echo "Resilience test passed."

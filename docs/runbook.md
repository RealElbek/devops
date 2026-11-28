# Runbook: what to do when something breaks

For whoever is on duty. Each entry: **symptom → check → fix → verify**.
The symptoms and outputs below were produced on the real stack (by stopping containers on purpose).

Related: setup and backups in [deployment.md](deployment.md) · architecture in [architecture.md](architecture.md).

---

## First 2 minutes (any problem)

```sh
make ps                                   # which container is not (healthy)?
open http://localhost                     # dashboard: the red box is the broken part
for s in event booking payment ticket; do echo "$s: $(curl -s -o /dev/null -w '%{http_code}' localhost/health/$s)"; done
docker compose logs --tail 50 <container> # e.g. booking-service, booking-db, gateway
```

| `/health/<svc>` answer | Meaning | Go to |
| ---------------------- | ------- | ----- |
| `200` | service and its database are fine | (look elsewhere) |
| `503` with `"service":"booking-service"` and a `"db"` error | the **service runs, its database is down** | [1](#1-a-database-is-down) |
| `503` with `{"error":"service unavailable"}` | the **service itself is down** (the gateway answered) | [2](#2-a-service-is-down) |
| no answer at all (`000`) | the **gateway is down** (or port 80 is blocked) | [3](#3-nothing-answers-on-port-80) |

Because each service has its own database, **one failure only breaks its own part**: with
`booking-db` down, `GET /api/v1/events` still returns `200` and ticket checks still work.

---

## 1. A database is down

**Symptom:** dashboard box `PostgreSQL · down` (red) under one service, which shows `running, database down`.
`/health/booking` → `503`, body contains `"db":"could not translate host name \"booking-db\"…"`.
Booking requests fail, the other services keep working.

**Check:**
```sh
docker compose ps booking-db
docker compose logs --tail 50 booking-db
```

**Fix:**
```sh
docker compose start booking-db           # or: docker compose up -d --wait booking-db
```
The service reconnects by itself (no restart needed). Measured: `/health/booking` back to `200` about 2 seconds after the database was healthy.

If it keeps crashing: read its log. Typical causes are a full disk (see [7](#7-disk-is-full)), or a
password changed in `.env` after the first start. Postgres keeps the password from the first start,
so either put the old one back or, on a **dev machine only**, `make clean` (⚠️ deletes all data).

**Verify:** `curl -s localhost/health/booking` → `{"status":"ok",…}` · `make smoke`

---

## 2. A service is down

**Symptom:** dashboard box `● not reachable` (red); its numbers show `—`.
`/health/booking` → `503 {"error":"service unavailable"}` (this answer comes from the gateway).
API calls for that service return `503`.

**Check:**
```sh
docker compose ps booking-service
docker compose logs --tail 100 booking-service      # Python traceback? DB connection error?
```

**Fix:**
```sh
docker compose up -d --wait booking-service
```
If it crashes again right away, it's a bug in the code or its config, so roll back (see [8](#8-a-release-is-bad-roll-back)).

**Verify:** `/health/booking` → `200` · dashboard box green · `make smoke`

---

## 3. Nothing answers on port 80

**Symptom:** browser can't open http://localhost; `curl localhost/` prints nothing (code `000`).

**Check:**
```sh
docker compose ps gateway
docker compose logs --tail 50 gateway     # nginx config error?
lsof -i :80                               # is something else using port 80?
```

**Fix:**
- Gateway stopped → `docker compose up -d --wait gateway`
- nginx config error after editing `nginx/nginx.conf` → `docker compose exec gateway nginx -t` shows the line; fix it and run `docker compose restart gateway`
- Port 80 taken by another program → set `HTTP_PORT=8000` in `.env`, run `make up`, use http://localhost:8000

**Verify:** `curl -s -o /dev/null -w '%{http_code}' localhost/` → `200`

---

## 4. `make up` fails or never becomes healthy

| What you see | Cause | Fix |
| ------------ | ----- | --- |
| `The "TICKET_DB_PASS" variable is not set` / `set TICKET_DB_PASS in .env` | `.env` is missing a line (old `.env` from before microservices) | copy the 4 `*_DB_PASS` lines from `.env.example` into `.env` |
| Waits up to 180 s, then reports a container as **unhealthy** | that container can't start properly (often: a service can't reach its DB) | `docker compose logs <that container>`, then see [1](#1-a-database-is-down) or [2](#2-a-service-is-down) |
| `Bind for 0.0.0.0:80 failed: port is already allocated` | port 80 in use | [3](#3-nothing-answers-on-port-80) |
| `Cannot connect to the Docker daemon` | Docker Desktop not running | start Docker Desktop, wait for the whale icon |

---

## 5. Data was deleted or corrupted

**Symptom:** e.g. tickets gone: `GET /api/v1/tickets/<code>` → `{"error":"ticket not found"}`.
On the dashboard, **Tickets sold** drops while **Bookings** still shows seats sold.

**Fix:** restore the last good backup (all 4 databases):
```sh
ls backups/                                   # pick the newest folder from BEFORE the problem
make restore FILE=backups/20261128-172121     # asks for 'yes'; saves a safety backup first
```
The 4 services are stopped for a few seconds (dashboard boxes go red, then green). That's expected.

**Verify:** the deleted data is back · `make smoke` · dashboard numbers add up again.

Data written **after** that backup is lost. That's why backups should run often (cron, see [deployment.md](deployment.md#backup-and-restore)).

---

## 6. A restore failed halfway

**Symptom:** `make restore` prints `Restore FAILED while restoring <db>` and lists which databases
were already restored. The services are started again automatically.

**Meaning:** the failed database is unchanged (each one restores in one transaction), but the
others are now from the backup, so **the databases are from different points in time**.

**Fix:** go back to the data from just before the restore. The script prints the exact command:
```sh
make restore FILE=backups/pre-restore-<timestamp>
```
Then find out why the backup file failed (the `pg_restore: error:` line) before trying again.

---

## 7. Disk is full

**Symptom:** a database or the build fails with `No space left on device`.

**Check / fix:**
```sh
docker system df                         # images, containers, volumes, build cache
du -sh backups/*                         # old backups
docker image prune -f                    # unused images (safe)
docker builder prune -f                  # build cache (safe)
BACKUP_KEEP=3 make backup                # keep fewer backups
```
⚠️ **Never** run `docker volume prune` or `make clean` to free space on a real server: they delete the databases.

---

## 8. A release is bad: roll back

**Symptom:** after a merge to `main`, a service misbehaves (errors in logs, smoke test fails).

**Fix (fastest):** revert the PR on GitHub (**Revert** button on the merged PR → new PR → CI → merge).
Or locally: `git revert <merge-commit>`, then push a branch and open a PR.

**With registry images** (from CI job *Publish images (GHCR)*): every `main` build is also tagged
`sha-<commit>`, so a server can go back to the exact previous version:
```sh
docker pull ghcr.io/realelbek/ticketing-booking-service:sha-<previous-commit>
```

---

## 9. CI is red on a pull request

| Failing job | What it means | What to do |
| ----------- | ------------- | ---------- |
| **Secret scan (gitleaks)** | a password/token is in the code or history | see [10](#10-a-secret-was-leaked) (**first** revoke it) |
| **Image scan (Trivy)** | a HIGH/CRITICAL vulnerability with a fix exists | open the log, find the package. OS package → rebuild (the Dockerfile runs `apt-get upgrade`); Python package → raise its version in `requirements.txt` |
| **Test &lt;svc&gt;-service** | lint or unit test failed | run `make test SERVICE=<svc>` locally, fix, push |
| **Full stack (smoke + resilience)** | services don't work together | run `make up && make smoke` locally; the job log ends with `docker compose logs` |

Never merge with a red check. Fix forward with a new commit on the same branch.

---

## 10. A secret was leaked

(A password, token or key ended up in a commit, an issue, a PR comment or a chat.)

1. **Revoke / rotate it first.** Deleting the text is not enough, because it stays in git history, caches and notifications.
   GitHub token: github.com/settings/tokens → Delete. DB password: change it in `.env` (and on the server).
2. Remove it from the code in a new PR; gitleaks must be green.
3. Tell the Tech Lead and the Security Champion; add a line to `docs/decisions.md` if a rule changes.

---

## 11. Bookings stay "pending" / seats look blocked

**Expected behaviour:** an unpaid booking holds its seats for `HOLD_MINUTES` (default 10), then
expires and the seats are released. The dashboard's **Seats on hold** shows how many are held.

**Check:** `curl -s localhost/api/v1/stats/booking` → `seats_held`, `by_status`.
If holds never expire, check that booking-service is healthy ([2](#2-a-service-is-down)) and that
`HOLD_MINUTES` in `.env` is what you expect, then `make up` to apply a change.

# EP10 — Real-World Docker Stack (Flask + Postgres + Nginx + cAdvisor)

DevOps exam task based on
[docker-home-lab-series / EP10-Real-world](https://github.com/learnwithdevopsengineer3682/docker-home-lab-series/tree/main/EP10-Real-world).

A small **production-like** stack orchestrated with Docker Compose:

```
              :80                         backend network (private)
 browser ───► nginx ──── reverse proxy ───► app (Flask + Gunicorn) ───► db (Postgres 14)
                                                                         │
                                                                   dbdata volume
 browser ───► cadvisor :8080   (CPU / memory / network of every container)
```

| Service    | Image                         | What it does                                              |
| ---------- | ----------------------------- | --------------------------------------------------------- |
| `nginx`    | `nginx:1.27-alpine`           | Only public entry point (port 80), proxies to Flask        |
| `app`      | built from `flask-app/`       | Flask app, runs as non-root, served by Gunicorn            |
| `db`       | `postgres:14-alpine`          | Database; data kept in the named volume `dbdata`           |
| `cadvisor` | `gcr.io/cadvisor/cadvisor`    | Container monitoring UI on port 8080                       |

## Files

```
docker-compose.yml   4 services, healthchecks, restart policies, 2 networks, 1 volume
nginx.conf           reverse proxy config (Lab 1)
flask-app/
  app.py             /  -> stores a visit in Postgres and returns the count
                     /health -> 200 only if DB is reachable (used by healthcheck)
  Dockerfile         python:3.12-slim, non-root user, HEALTHCHECK, gunicorn
  requirements.txt   pinned versions
.env.example         DB credentials template (real .env is git-ignored)
.github/workflows/ci.yml   GitHub Actions: starts the stack and tests it
```

## Quick start

Requirements: Docker + Docker Compose v2.

```sh
cp .env.example .env                       # set DB_USER, DB_PASS, DB_NAME
docker compose up --build -d --wait        # build + start, wait until healthy
docker compose ps                          # all 4 should be (healthy)
```

Open:
- App via Nginx: <http://localhost>
- App health: <http://localhost/health>
- cAdvisor: <http://localhost:8080>

Stop: `docker compose down` (data is kept) · Delete everything incl. data: `docker compose down -v`

---

## Lab 1 — Reverse proxy

`nginx` is the **only** service with a public port (`80:80`). The Flask app uses `expose: 5000`,
so it is reachable only inside the Docker network. `nginx.conf` forwards every request to
`http://app:5000` (Docker DNS resolves the service name `app`) and passes the real client
headers (`X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`).

```sh
$ curl http://localhost/
{"message":"Hello from the EP10 real-world Docker stack!","served_by":"4c343b6a1cb1","visits":1}
```

## Lab 2 — Health checks

| Service | Healthcheck                                    |
| ------- | ---------------------------------------------- |
| `db`    | `pg_isready -U $POSTGRES_USER -d $POSTGRES_DB` |
| `app`   | `GET /health` → also runs `SELECT 1` on the DB |
| `nginx` | `GET /nginx-health`                            |

`depends_on` alone only controls **start order**, not readiness. Here we use
`condition: service_healthy`, so: `db` healthy → `app` starts → `app` healthy → `nginx` starts.

```sh
$ docker compose ps
NAME                IMAGE                              SERVICE    STATUS
devops-app-1        ep10-flask-app:latest              app        Up 25 seconds (healthy)
devops-cadvisor-1   gcr.io/cadvisor/cadvisor:v0.49.1   cadvisor   Up 30 seconds (healthy)
devops-db-1         postgres:14-alpine                 db         Up 30 seconds (healthy)
devops-nginx-1      nginx:1.27-alpine                  nginx      Up 19 seconds (healthy)
```

## Lab 3 — Monitoring with cAdvisor

cAdvisor mounts the host's `/sys`, `/var/run`, `/var/lib/docker` (read-only) and shows live CPU,
memory, network and filesystem usage per container at <http://localhost:8080> →
**Docker Containers**.

Resource usage measured on the running stack (`docker stats --no-stream`):

| Container | CPU    | Memory  | Notes                                        |
| --------- | ------ | ------- | -------------------------------------------- |
| nginx     | ~0%    | ~4 MiB  | very light, just proxies                     |
| app       | low    | ~56 MiB | heaviest: Python + 2 Gunicorn workers        |
| db        | ~1%    | ~19 MiB | grows with data / connections                |
| cadvisor  | ~0.4%  | ~19 MiB | monitoring overhead is small                 |

If the app became a bottleneck, the next step would be more Gunicorn workers or more `app`
replicas behind Nginx, and setting `deploy.resources.limits` per service.

## Production practices used

- **Restart policy** `unless-stopped` on every service — containers come back after a crash/reboot.
- **Named volume** `dbdata` — data survives `docker compose down` (visit counter keeps growing).
- **Secrets in `.env`**, not in git; `.env.example` is the template.
- **Non-root user** in the app image; small `slim`/`alpine` images; pinned versions.
- **Gunicorn** instead of Flask's dev server.
- **Network isolation** — `db` and `app` live only on the `backend` network; only Nginx
  (port 80) and cAdvisor (port 8080) are published.
- **CI** — GitHub Actions starts the full stack, waits for healthchecks, tests the app through
  Nginx, checks persistence after `down`/`up`, and checks cAdvisor.

## Useful commands

```sh
docker compose logs -f app            # follow app logs
docker inspect --format '{{json .State.Health}}' devops-app-1   # healthcheck details
docker compose exec db psql -U flaskuser -d flaskdb -c 'SELECT count(*) FROM visits;'
docker compose restart app            # restart one service
```

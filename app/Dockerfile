# Multi-stage build:  base (deps) -> test (pytest + ruff) -> runtime (small, non-root)
FROM python:3.15-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# ---------- test image: used by `make test` and CI ----------
FROM base AS test
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
COPY pyproject.toml .
COPY ticketing/ ticketing/
COPY tests/ tests/
CMD ["sh", "-c", "ruff check . && pytest -v"]

# ---------- runtime image: what actually runs ----------
FROM base AS runtime
LABEL org.opencontainers.image.title="ticket-booking" \
      org.opencontainers.image.source="https://github.com/RealElbek/devops"
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser
COPY --chown=root:root ticketing/ ticketing/
USER appuser
EXPOSE 5000
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
  CMD ["python", "-c", "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=2).status == 200 else 1)"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", \
     "--access-logfile", "-", "--worker-tmp-dir", "/tmp", "ticketing:create_app()"]

# booking-service image. Build context is ./services (so the shared "common" package can be copied in).
# Multi-stage: base (deps) -> test (ruff + pytest) -> runtime (small, non-root)
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
# OS security fixes released after the python base image was built (Trivy fails CI on fixable HIGH/CRITICAL)
RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY booking-service/requirements.txt .
RUN pip install -r requirements.txt
COPY common/ common/

# ---------- test image: used by `make test` and CI ----------
FROM base AS test
COPY requirements-dev.txt pyproject.toml ./
RUN pip install -r requirements-dev.txt
COPY booking-service/booking_service/ booking_service/
COPY booking-service/tests/ tests/
CMD ["sh", "-c", "ruff check . && pytest -v"]

# ---------- runtime image: what actually runs ----------
FROM base AS runtime
LABEL org.opencontainers.image.title="booking-service" \
      org.opencontainers.image.source="https://github.com/RealElbek/devops"
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser
COPY booking-service/booking_service/ booking_service/
USER appuser
EXPOSE 5000
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
  CMD ["python", "-c", "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=2).status == 200 else 1)"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", \
     "--access-logfile", "-", "--worker-tmp-dir", "/tmp", "booking_service:create_app()"]

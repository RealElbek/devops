"""Database helpers: one short-lived connection per unit of work."""

import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

log = logging.getLogger(__name__)

SCHEMA_FILE = Path(__file__).with_name("schema.sql")
# Any constant: makes schema creation safe when several replicas start at once.
SCHEMA_LOCK_ID = 4242


def connect(dbname=None):
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "db"),
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname=dbname or os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASS"],
        connect_timeout=3,
        cursor_factory=RealDictCursor,
    )


@contextmanager
def transaction():
    """Yield a cursor inside a transaction: commit on success, roll back on error."""
    conn = connect()
    try:
        with conn:  # commits or rolls back
            with conn.cursor() as cur:
                yield cur
    finally:
        conn.close()


def ping():
    with transaction() as cur:
        cur.execute("SELECT 1 AS ok")
        return cur.fetchone()["ok"] == 1


def init_schema(retries=20, delay=1.5):
    """Create tables. Retries so the app survives starting before Postgres is ready."""
    for attempt in range(1, retries + 1):
        try:
            with transaction() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(%s)", (SCHEMA_LOCK_ID,))
                cur.execute(SCHEMA_FILE.read_text())
            log.info("database schema ready")
            return
        except psycopg2.OperationalError as e:
            log.warning("database not ready (attempt %s/%s): %s", attempt, retries, e)
            time.sleep(delay)
    raise RuntimeError("could not initialise database schema")

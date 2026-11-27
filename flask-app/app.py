import os
import socket

import psycopg2
from flask import Flask, jsonify

app = Flask(__name__)


def get_conn():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "db"),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASS"],
        connect_timeout=3,
    )


def init_db():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "CREATE TABLE IF NOT EXISTS visits ("
            " id SERIAL PRIMARY KEY,"
            " visited_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )


@app.route("/")
def home():
    """Every request is stored in Postgres, so the counter proves data persists."""
    try:
        init_db()
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO visits DEFAULT VALUES")
            cur.execute("SELECT count(*) FROM visits")
            total = cur.fetchone()[0]
        return jsonify(
            message="Hello from the EP10 real-world Docker stack!",
            visits=total,
            served_by=socket.gethostname(),
        )
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.route("/health")
def health():
    """Used by the Docker healthcheck: healthy only if the database answers."""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
        return jsonify(status="ok", db="ok")
    except Exception as e:
        return jsonify(status="error", db=str(e)), 503


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

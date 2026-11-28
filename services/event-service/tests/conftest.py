"""Integration tests against a REAL Postgres (a separate *_test database)."""

import os

import pytest

os.environ["DB_NAME"] = os.environ.get("TEST_DB_NAME", "events_test")
os.environ["SEED_DEMO"] = "false"

from common import db  # noqa: E402
from event_service import create_app  # noqa: E402


@pytest.fixture(scope="session")
def app():
    db.ensure_database(os.environ["DB_NAME"])
    return create_app()


@pytest.fixture(autouse=True)
def clean_db(app):
    with db.transaction() as cur:
        cur.execute("TRUNCATE seats, events RESTART IDENTITY CASCADE")


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def event(client):
    res = client.post(
        "/api/v1/events",
        json={
            "title": "Test Concert",
            "venue": "Test Hall",
            "starts_at": "2026-12-31T19:00:00+05:00",
            "rows": 2,
            "seats_per_row": 5,
            "price": 100000,
        },
    )
    assert res.status_code == 201, res.json
    return res.json

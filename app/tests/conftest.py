"""Integration tests run against a REAL Postgres (a separate *_test database)."""

import os

import pytest

os.environ["DB_NAME"] = os.environ.get("TEST_DB_NAME", "ticketing_test")
os.environ["SEED_DEMO"] = "false"

from ticketing import create_app, db  # noqa: E402


def _ensure_test_database():
    conn = db.connect(dbname="postgres")
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (os.environ["DB_NAME"],))
        if not cur.fetchone():
            cur.execute(f'CREATE DATABASE "{os.environ["DB_NAME"]}"')
    conn.close()


@pytest.fixture(scope="session")
def app():
    _ensure_test_database()
    return create_app()


@pytest.fixture(autouse=True)
def clean_db(app):
    with db.transaction() as cur:
        cur.execute(
            "TRUNCATE tickets, payments, booking_seats, bookings, seats, events "
            "RESTART IDENTITY CASCADE"
        )


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


@pytest.fixture
def seats(client, event):
    return client.get(f"/api/v1/events/{event['id']}/seats").json


def book(client, event_id, seat_ids, name="Ali Valiyev", email="ali@example.com"):
    return client.post(
        "/api/v1/bookings",
        json={
            "event_id": event_id,
            "seat_ids": seat_ids,
            "customer_name": name,
            "customer_email": email,
        },
    )

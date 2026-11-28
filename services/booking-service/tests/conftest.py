"""Integration tests against a REAL Postgres (a separate *_test database).

event-service is replaced by an in-memory fake: these tests check booking-service alone.
The real services talking to each other are tested by scripts/smoke_test.sh.
"""

import os

import pytest

os.environ["DB_NAME"] = os.environ.get("TEST_DB_NAME", "bookings_test")

from booking_service import clients, create_app  # noqa: E402
from common import db  # noqa: E402
from common.errors import ApiError  # noqa: E402

EVENT_ID = 1
# Fake seat map of event 1: 2 rows x 5 seats, ids 1..10, 100 000 UZS each
SEATS = [
    {"id": i + 1, "label": f"{'AB'[i // 5]}{i % 5 + 1}", "price": 100000} for i in range(10)
]


def _fake_event_seats(event_id):
    if event_id != EVENT_ID:
        raise ApiError(404, "event not found")
    return [dict(s) for s in SEATS]


def _fake_lookup_seats(event_id, seat_ids):
    return [s for s in _fake_event_seats(event_id) if s["id"] in seat_ids]


@pytest.fixture(scope="session")
def app():
    db.ensure_database(os.environ["DB_NAME"])
    return create_app()


@pytest.fixture(autouse=True)
def fake_event_service(monkeypatch):
    monkeypatch.setattr(clients, "event_seats", _fake_event_seats)
    monkeypatch.setattr(clients, "lookup_seats", _fake_lookup_seats)


@pytest.fixture(autouse=True)
def clean_db(app):
    with db.transaction() as cur:
        cur.execute("TRUNCATE booking_seats, bookings RESTART IDENTITY CASCADE")


@pytest.fixture
def client(app):
    return app.test_client()


def book(client, seat_ids, name="Ali Valiyev", email="ali@example.com", event_id=EVENT_ID):
    return client.post(
        "/api/v1/bookings",
        json={
            "event_id": event_id,
            "seat_ids": seat_ids,
            "customer_name": name,
            "customer_email": email,
        },
    )

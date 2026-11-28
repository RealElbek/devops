"""Integration tests against a REAL Postgres (a separate *_test database).

event-service is replaced by an in-memory fake.
"""

import os

import pytest

os.environ["DB_NAME"] = os.environ.get("TEST_DB_NAME", "tickets_test")

from common import db  # noqa: E402
from common.errors import ApiError  # noqa: E402
from ticket_service import clients, create_app  # noqa: E402

EVENT = {
    "id": 1,
    "title": "Test Concert",
    "venue": "Test Hall",
    "starts_at": "2026-12-31T19:00:00+05:00",
}


def _fake_get_event(event_id):
    if event_id != EVENT["id"]:
        raise ApiError(404, "event not found")
    return dict(EVENT)


@pytest.fixture(scope="session")
def app():
    db.ensure_database(os.environ["DB_NAME"])
    return create_app()


@pytest.fixture(autouse=True)
def fake_event_service(monkeypatch):
    monkeypatch.setattr(clients, "get_event", _fake_get_event)


@pytest.fixture(autouse=True)
def clean_db(app):
    with db.transaction() as cur:
        cur.execute("TRUNCATE tickets RESTART IDENTITY")


@pytest.fixture
def client(app):
    return app.test_client()


def issue(client, booking_id=1, seats=((1, "A1"), (2, "A2"))):
    return client.post(
        "/internal/tickets",
        json={
            "booking_id": booking_id,
            "event_id": EVENT["id"],
            "customer_name": "Ali Valiyev",
            "seats": [{"seat_id": sid, "label": label} for sid, label in seats],
        },
    )

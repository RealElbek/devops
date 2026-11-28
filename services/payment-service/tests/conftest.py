"""Integration tests against a REAL Postgres (a separate *_test database).

booking-service and ticket-service are replaced by in-memory fakes, so we can also simulate
them failing in the middle of a payment.
"""

import os

import pytest

os.environ["DB_NAME"] = os.environ.get("TEST_DB_NAME", "payments_test")

from common import db  # noqa: E402
from common.errors import ApiError  # noqa: E402
from payment_service import clients, create_app  # noqa: E402


class FakeServices:
    def __init__(self):
        self.bookings = {}
        self.tickets = {}
        self.ticket_service_down = False
        self.booking_service_down = False
        self.expire_before_mark_paid = False

    def add_booking(self, booking_id, status="pending", seats=("A1", "A2")):
        self.bookings[booking_id] = {
            "id": booking_id,
            "event_id": 1,
            "customer_name": "Ali Valiyev",
            "status": status,
            "total": 100000 * len(seats),
            "seats": [{"id": i + 1, "label": label} for i, label in enumerate(seats)],
        }
        return booking_id

    # --- booking-service ---
    def get_booking(self, booking_id):
        if booking_id not in self.bookings:
            raise ApiError(404, "booking not found")
        return dict(self.bookings[booking_id])

    def mark_paid(self, booking_id):
        if self.booking_service_down:
            raise ApiError(503, "booking-service unavailable")
        booking = self.bookings[booking_id]
        if self.expire_before_mark_paid:
            booking["status"] = "expired"
        if booking["status"] == "pending":
            booking["status"] = "paid"
        elif booking["status"] != "paid":
            raise ApiError(409, f"booking cannot be paid (status: {booking['status']})")
        return dict(booking)

    # --- ticket-service ---
    def issue_tickets(self, booking):
        if self.ticket_service_down:
            raise ApiError(503, "ticket-service unavailable")
        if booking["id"] in self.tickets:
            return {"created": False, "tickets": self.tickets[booking["id"]]}
        tickets = [{"code": f"TKT-{booking['id']}-{s['id']}", "seat": s["label"]}
                   for s in booking["seats"]]
        self.tickets[booking["id"]] = tickets
        return {"created": True, "tickets": tickets}


@pytest.fixture(scope="session")
def app():
    db.ensure_database(os.environ["DB_NAME"])
    return create_app()


@pytest.fixture
def fake(monkeypatch):
    services = FakeServices()
    for name in ("get_booking", "mark_paid", "issue_tickets"):
        monkeypatch.setattr(clients, name, getattr(services, name))
    return services


@pytest.fixture(autouse=True)
def clean_db(app):
    with db.transaction() as cur:
        cur.execute("TRUNCATE payments RESTART IDENTITY")


@pytest.fixture
def client(app, fake):
    return app.test_client()


def pay(client, booking_id, method="card"):
    return client.post(f"/api/v1/bookings/{booking_id}/pay", json={"method": method})

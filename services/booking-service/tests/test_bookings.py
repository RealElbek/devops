import threading

from booking_service import clients
from common import db
from common.errors import ApiError
from conftest import EVENT_ID, book


def available(client):
    return client.get(f"/api/v1/events/{EVENT_ID}/availability").json["available_seats"]


def test_health(client):
    assert client.get("/health").json["service"] == "booking-service"


def test_booking_holds_seats(client):
    res = book(client, [1, 2])
    assert res.status_code == 201
    assert res.json["status"] == "pending"
    assert res.json["total"] == 200000
    assert [s["label"] for s in res.json["seats"]] == ["A1", "A2"]
    assert available(client) == 8


def test_availability_marks_taken_seats(client):
    book(client, [3])
    seats = client.get(f"/api/v1/events/{EVENT_ID}/availability").json["seats"]
    assert [s["label"] for s in seats if not s["available"]] == ["A3"]
    assert client.get("/api/v1/events/999/availability").status_code == 404


def test_same_seat_cannot_be_booked_twice(client):
    assert book(client, [1]).status_code == 201
    res = book(client, [1, 2], email="b@example.com")
    assert res.status_code == 409
    assert "A1" in res.json["error"]


def test_booking_validation(client):
    assert book(client, []).status_code == 400
    assert book(client, [1, 1]).status_code == 400
    assert book(client, [1], email="not-an-email").status_code == 400
    assert book(client, [1], name=" ").status_code == 400
    assert book(client, [99999]).status_code == 404
    assert book(client, [1], event_id=999).status_code == 404


def test_cancel_releases_seats(client):
    booking = book(client, [1]).json
    assert client.post(f"/api/v1/bookings/{booking['id']}/cancel").json["status"] == "cancelled"
    assert book(client, [1], email="c@example.com").status_code == 201


def test_expired_hold_releases_seat(client):
    booking = book(client, [1]).json
    with db.transaction() as cur:
        cur.execute(
            "UPDATE bookings SET expires_at = now() - interval '1 minute' WHERE id = %s",
            (booking["id"],),
        )
    assert client.get(f"/api/v1/bookings/{booking['id']}").json["status"] == "expired"
    assert client.post(f"/internal/bookings/{booking['id']}/mark-paid").status_code == 409
    assert book(client, [1], email="d@example.com").status_code == 201


def test_mark_paid_is_idempotent_and_blocks_cancel(client):
    booking = book(client, [1]).json
    url = f"/internal/bookings/{booking['id']}/mark-paid"
    assert client.post(url).json["status"] == "paid"
    assert client.post(url).json["status"] == "paid"  # second call is safe
    assert client.post(f"/api/v1/bookings/{booking['id']}/cancel").status_code == 409
    assert book(client, [1], email="e@example.com").status_code == 409  # paid seat stays taken


def test_event_service_down_returns_503(client, monkeypatch):
    def down(*_):
        raise ApiError(503, "event-service unavailable")

    monkeypatch.setattr(clients, "lookup_seats", down)
    res = book(client, [1])
    assert res.status_code == 503
    assert res.json["error"] == "event-service unavailable"


def test_concurrent_bookings_only_one_wins(app):
    """20 people click the same seat at the same moment: exactly one gets it."""
    results = []

    def attempt(i):
        res = book(app.test_client(), [5], email=f"user{i}@example.com")
        results.append(res.status_code)

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count(201) == 1
    assert results.count(409) == 19


def test_stats_counts_bookings_and_seats(client):
    paid = book(client, [1, 2]).json
    client.post(f"/internal/bookings/{paid['id']}/mark-paid")
    book(client, [3], email="h@example.com")                       # active hold
    cancelled = book(client, [4], email="c@example.com").json
    client.post(f"/api/v1/bookings/{cancelled['id']}/cancel")
    old = book(client, [5], email="o@example.com").json            # hold that ran out
    with db.transaction() as cur:
        cur.execute(
            "UPDATE bookings SET expires_at = now() - interval '1 minute' WHERE id = %s",
            (old["id"],),
        )
    res = client.get("/api/v1/stats").json
    assert res["bookings"] == 4
    assert res["by_status"] == {"pending": 1, "paid": 1, "cancelled": 1, "expired": 1}
    assert res["seats_sold"] == 2
    assert res["seats_held"] == 1

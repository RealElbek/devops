import threading

from conftest import book
from ticketing import db


def test_booking_holds_seats(client, event, seats):
    res = book(client, event["id"], [seats[0]["id"], seats[1]["id"]])
    assert res.status_code == 201
    assert res.json["status"] == "pending"
    assert res.json["total"] == 200000
    assert client.get(f"/api/v1/events/{event['id']}").json["available_seats"] == 8


def test_same_seat_cannot_be_booked_twice(client, event, seats):
    assert book(client, event["id"], [seats[0]["id"]]).status_code == 201
    res = book(client, event["id"], [seats[0]["id"], seats[1]["id"]], email="b@example.com")
    assert res.status_code == 409
    assert "A1" in res.json["error"]


def test_booking_validation(client, event, seats):
    sid = seats[0]["id"]
    assert book(client, event["id"], []).status_code == 400
    assert book(client, event["id"], [sid, sid]).status_code == 400
    assert book(client, event["id"], [sid], email="not-an-email").status_code == 400
    assert book(client, event["id"], [sid], name=" ").status_code == 400
    assert book(client, event["id"], [99999]).status_code == 404


def test_cancel_releases_seats(client, event, seats):
    booking = book(client, event["id"], [seats[0]["id"]]).json
    res = client.post(f"/api/v1/bookings/{booking['id']}/cancel")
    assert res.json["status"] == "cancelled"
    assert book(client, event["id"], [seats[0]["id"]], email="c@example.com").status_code == 201


def test_expired_hold_releases_seat(client, event, seats):
    booking = book(client, event["id"], [seats[0]["id"]]).json
    with db.transaction() as cur:
        cur.execute(
            "UPDATE bookings SET expires_at = now() - interval '1 minute' WHERE id = %s",
            (booking["id"],),
        )
    assert client.get(f"/api/v1/bookings/{booking['id']}").json["status"] == "expired"
    assert client.post(
        f"/api/v1/bookings/{booking['id']}/pay", json={"method": "card"}
    ).status_code == 409
    assert book(client, event["id"], [seats[0]["id"]], email="d@example.com").status_code == 201


def test_concurrent_bookings_only_one_wins(app, event, seats):
    """20 people click the same seat at the same moment: exactly one gets it."""
    seat_id = seats[0]["id"]
    results = []

    def attempt(i):
        res = book(app.test_client(), event["id"], [seat_id], email=f"user{i}@example.com")
        results.append(res.status_code)

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count(201) == 1
    assert results.count(409) == 19

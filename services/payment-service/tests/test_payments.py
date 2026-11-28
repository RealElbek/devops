from conftest import pay


def payment_status(client, booking_id):
    res = client.get(f"/api/v1/payments/{booking_id}")
    return res.json["status"] if res.status_code == 200 else res.status_code


def test_health(client):
    assert client.get("/health").json["service"] == "payment-service"


def test_pay_marks_booking_paid_and_issues_tickets(client, fake):
    booking_id = fake.add_booking(1)
    res = pay(client, booking_id, "click")
    assert res.status_code == 200
    assert res.json["status"] == "paid"
    assert res.json["payment"]["amount"] == 200000
    assert res.json["payment"]["status"] == "succeeded"
    assert res.json["payment"]["method"] == "click"
    assert [t["seat"] for t in res.json["tickets"]] == ["A1", "A2"]
    assert fake.bookings[booking_id]["status"] == "paid"


def test_cannot_pay_twice(client, fake):
    booking_id = fake.add_booking(1)
    assert pay(client, booking_id).status_code == 200
    res = pay(client, booking_id)
    assert res.status_code == 409
    assert res.json["error"] == "booking is already paid"


def test_cannot_pay_cancelled_or_expired(client, fake):
    assert pay(client, fake.add_booking(1, status="cancelled")).status_code == 409
    assert pay(client, fake.add_booking(2, status="expired")).status_code == 409
    assert payment_status(client, 1) == 404  # nothing recorded


def test_hold_expires_during_payment_records_failed(client, fake):
    booking_id = fake.add_booking(1)
    fake.expire_before_mark_paid = True  # the 10-minute hold runs out while paying
    assert pay(client, booking_id).status_code == 409
    assert payment_status(client, booking_id) == "failed"


def test_validation_and_unknown_booking(client, fake):
    booking_id = fake.add_booking(1)
    assert pay(client, booking_id, "bitcoin").status_code == 400
    assert pay(client, 999).status_code == 404


def test_ticket_service_down_then_retry_finishes_payment(client, fake):
    booking_id = fake.add_booking(1)
    fake.ticket_service_down = True
    res = pay(client, booking_id)
    assert res.status_code == 503
    assert payment_status(client, booking_id) == "succeeded"  # money taken, tickets pending

    fake.ticket_service_down = False
    res = pay(client, booking_id)  # retry continues where it stopped
    assert res.status_code == 200
    assert len(res.json["tickets"]) == 2


def test_booking_service_down_records_nothing(client, fake):
    booking_id = fake.add_booking(1)
    fake.booking_service_down = True
    assert pay(client, booking_id).status_code == 503
    assert payment_status(client, booking_id) == 404  # rolled back, safe to retry
    fake.booking_service_down = False
    assert pay(client, booking_id).status_code == 200


def test_stats_revenue_only_counts_succeeded(client, fake):
    pay(client, fake.add_booking(1), "click")                       # 200 000 UZS
    pay(client, fake.add_booking(2, seats=("B1",)), "cash")        # 100 000 UZS
    fake.expire_before_mark_paid = True
    pay(client, fake.add_booking(3))                                # failed
    res = client.get("/api/v1/stats").json
    assert res["payments"] == 3
    assert res["revenue"] == 300000
    assert res["failed"] == 1
    assert res["by_method"] == {"card": 0, "click": 1, "payme": 0, "cash": 1}

from conftest import book


def test_pay_issues_one_ticket_per_seat(client, event, seats):
    booking = book(client, event["id"], [seats[0]["id"], seats[1]["id"]]).json
    res = client.post(f"/api/v1/bookings/{booking['id']}/pay", json={"method": "click"})
    assert res.status_code == 200
    paid = res.json
    assert paid["status"] == "paid"
    assert paid["payment"]["amount"] == 200000
    assert paid["payment"]["status"] == "succeeded"
    assert [t["seat"] for t in paid["tickets"]] == ["A1", "A2"]
    assert all(t["code"].startswith("TKT-") for t in paid["tickets"])


def test_ticket_lookup(client, event, seats):
    booking = book(client, event["id"], [seats[0]["id"]]).json
    paid = client.post(f"/api/v1/bookings/{booking['id']}/pay", json={"method": "card"}).json
    code = paid["tickets"][0]["code"]
    res = client.get(f"/api/v1/tickets/{code.lower()}")
    assert res.status_code == 200
    assert res.json["seat"] == "A1"
    assert res.json["event"] == "Test Concert"
    assert client.get("/api/v1/tickets/TKT-0000-0000").status_code == 404


def test_cannot_pay_twice_or_cancel_paid(client, event, seats):
    booking = book(client, event["id"], [seats[0]["id"]]).json
    url = f"/api/v1/bookings/{booking['id']}"
    assert client.post(f"{url}/pay", json={"method": "payme"}).status_code == 200
    assert client.post(f"{url}/pay", json={"method": "payme"}).status_code == 409
    assert client.post(f"{url}/cancel").status_code == 409


def test_paid_seat_stays_taken(client, event, seats):
    booking = book(client, event["id"], [seats[0]["id"]]).json
    client.post(f"/api/v1/bookings/{booking['id']}/pay", json={"method": "cash"})
    assert book(client, event["id"], [seats[0]["id"]], email="x@example.com").status_code == 409


def test_invalid_payment_method(client, event, seats):
    booking = book(client, event["id"], [seats[0]["id"]]).json
    res = client.post(f"/api/v1/bookings/{booking['id']}/pay", json={"method": "bitcoin"})
    assert res.status_code == 400

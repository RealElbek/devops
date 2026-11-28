from conftest import issue


def test_health(client):
    assert client.get("/health").json["service"] == "ticket-service"


def test_issue_one_ticket_per_seat(client):
    res = issue(client)
    assert res.status_code == 201
    assert res.json["created"] is True
    assert [t["seat"] for t in res.json["tickets"]] == ["A1", "A2"]
    assert all(t["code"].startswith("TKT-") for t in res.json["tickets"])


def test_issue_is_idempotent(client):
    first = issue(client).json["tickets"]
    res = issue(client)
    assert res.status_code == 200
    assert res.json["created"] is False
    assert res.json["tickets"] == first  # same codes, nothing new


def test_ticket_lookup_copies_event_details(client):
    code = issue(client).json["tickets"][0]["code"]
    res = client.get(f"/api/v1/tickets/{code.lower()}")
    assert res.status_code == 200
    assert res.json["seat"] == "A1"
    assert res.json["event"] == "Test Concert"
    assert res.json["customer_name"] == "Ali Valiyev"
    assert client.get("/api/v1/tickets/TKT-0000-0000").status_code == 404


def test_same_seat_can_never_get_two_tickets(client):
    assert issue(client, booking_id=1, seats=[(1, "A1")]).status_code == 201
    res = issue(client, booking_id=2, seats=[(1, "A1")])
    assert res.status_code == 409


def test_tickets_for_booking(client):
    issue(client)
    res = client.get("/api/v1/tickets?booking_id=1")
    assert [t["seat"] for t in res.json] == ["A1", "A2"]
    assert client.get("/api/v1/tickets").status_code == 400


def test_issue_validation_and_unknown_event(client):
    assert client.post("/internal/tickets", json={"booking_id": 1}).status_code == 400
    res = client.post(
        "/internal/tickets",
        json={"booking_id": 1, "event_id": 999, "customer_name": "X",
              "seats": [{"seat_id": 1, "label": "A1"}]},
    )
    assert res.status_code == 404

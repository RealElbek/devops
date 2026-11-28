import threading

from event_service import service


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json["db"] == "ok"
    assert res.json["service"] == "event-service"


def test_create_event_generates_seats(client, event):
    assert event["total_seats"] == 10
    seats = client.get(f"/api/v1/events/{event['id']}/seats").json
    assert [s["label"] for s in seats[:6]] == ["A1", "A2", "A3", "A4", "A5", "B1"]
    assert all(s["price"] == 100000 for s in seats)


def test_list_and_get_events(client, event):
    assert [e["id"] for e in client.get("/api/v1/events").json] == [event["id"]]
    assert client.get(f"/api/v1/events/{event['id']}").json["title"] == "Test Concert"


def test_create_event_validation(client):
    res = client.post("/api/v1/events", json={"title": "x", "venue": "y", "starts_at": "bad"})
    assert res.status_code == 400
    res = client.post("/api/v1/events", data="not json", content_type="text/plain")
    assert res.status_code == 400


def test_unknown_event_is_404(client):
    assert client.get("/api/v1/events/999").status_code == 404
    assert client.get("/api/v1/events/999/seats").status_code == 404


def test_internal_seat_lookup_only_returns_seats_of_that_event(client, event):
    seats = client.get(f"/api/v1/events/{event['id']}/seats").json
    res = client.post(
        "/internal/seats/lookup",
        json={"event_id": event["id"], "seat_ids": [seats[0]["id"], 99999]},
    )
    assert res.status_code == 200
    assert [s["label"] for s in res.json] == ["A1"]
    res = client.post("/internal/seats/lookup", json={"event_id": 999, "seat_ids": [1]})
    assert res.status_code == 404


def test_demo_seed_runs_once_even_in_parallel(app):
    threads = [threading.Thread(target=service.seed_demo) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(service.list_events()) == 1

"""Event catalog: events and their seat maps (labels and prices).

This service does NOT know which seats are booked: that belongs to booking-service.
"""

from datetime import datetime

from common.db import transaction
from common.errors import ApiError


def _row_label(index):
    """0 -> A, 25 -> Z, 26 -> AA ..."""
    label = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        label = chr(65 + rem) + label
    return label


def create_event(data, only_if_empty=False):
    """Create an event and its seats. only_if_empty=True is used for demo seeding."""
    title = (data.get("title") or "").strip()
    venue = (data.get("venue") or "").strip()
    rows = data.get("rows")
    per_row = data.get("seats_per_row")
    price = data.get("price")
    if not title or not venue:
        raise ApiError(400, "title and venue are required")
    try:
        starts_at = datetime.fromisoformat(str(data.get("starts_at")))
    except ValueError:
        msg = "starts_at must be ISO format, e.g. 2026-12-31T19:00:00+05:00"
        raise ApiError(400, msg) from None
    for name, value, limit in (("rows", rows, 52), ("seats_per_row", per_row, 100)):
        if not isinstance(value, int) or not 1 <= value <= limit:
            raise ApiError(400, f"{name} must be an integer between 1 and {limit}")
    if not isinstance(price, int) or price < 0:
        raise ApiError(400, "price must be a non-negative integer (UZS)")

    with transaction() as cur:
        if only_if_empty:
            # Check + insert under one lock, so parallel workers/replicas seed only once.
            cur.execute("SELECT pg_advisory_xact_lock(4243)")
            cur.execute("SELECT count(*) AS n FROM events")
            if cur.fetchone()["n"]:
                return None
        cur.execute(
            "INSERT INTO events (title, venue, starts_at) VALUES (%s, %s, %s) RETURNING id",
            (title, venue, starts_at),
        )
        event_id = cur.fetchone()["id"]
        seats = [
            (event_id, f"{_row_label(r)}{n}", price)
            for r in range(rows)
            for n in range(1, per_row + 1)
        ]
        cur.executemany("INSERT INTO seats (event_id, label, price) VALUES (%s, %s, %s)", seats)
    return get_event(event_id)


EVENT_SQL = """
    SELECT e.id, e.title, e.venue, e.starts_at, count(s.id) AS total_seats
    FROM events e
    LEFT JOIN seats s ON s.event_id = e.id
"""


def list_events():
    with transaction() as cur:
        cur.execute(EVENT_SQL + " GROUP BY e.id ORDER BY e.starts_at, e.id")
        return cur.fetchall()


def get_event(event_id):
    with transaction() as cur:
        cur.execute(EVENT_SQL + " WHERE e.id = %s GROUP BY e.id", (event_id,))
        event = cur.fetchone()
    if not event:
        raise ApiError(404, "event not found")
    return event


def list_seats(event_id):
    get_event(event_id)
    with transaction() as cur:
        cur.execute(
            "SELECT id, label, price FROM seats WHERE event_id = %s ORDER BY id", (event_id,)
        )
        return cur.fetchall()


def lookup_seats(data):
    """Internal: return the requested seats of one event (used by booking-service)."""
    event_id = data.get("event_id")
    seat_ids = data.get("seat_ids")
    if not isinstance(event_id, int) or not isinstance(seat_ids, list):
        raise ApiError(400, "event_id (int) and seat_ids (list) are required")
    get_event(event_id)
    with transaction() as cur:
        cur.execute(
            "SELECT id, label, price FROM seats WHERE event_id = %s AND id = ANY(%s) ORDER BY id",
            (event_id, seat_ids),
        )
        return cur.fetchall()


def stats():
    """Numbers for the dashboard: only this service's own data."""
    with transaction() as cur:
        cur.execute(
            "SELECT count(*) AS events, "
            "count(*) FILTER (WHERE starts_at > now()) AS upcoming_events, "
            "(SELECT count(*) FROM seats) AS seats FROM events"
        )
        return cur.fetchone()


def seed_demo():
    """Create one demo event on first start so the API is not empty."""
    create_event(
        {
            "title": "Tashkent DevOps Live 2026",
            "venue": "Tashkent, Humo Arena",
            "starts_at": "2026-12-20T19:00:00+05:00",
            "rows": 5,
            "seats_per_row": 10,
            "price": 150000,
        },
        only_if_empty=True,
    )

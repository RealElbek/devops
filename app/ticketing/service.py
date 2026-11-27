"""Business rules for events, seats, bookings, payments and tickets.

The key rule: a seat can never be sold twice.
  1. Booking a seat locks its row (SELECT ... FOR UPDATE), so two people clicking the
     same seat at the same moment are handled one after the other.
  2. tickets.seat_id is UNIQUE, so even a bug cannot issue two tickets for one seat.
"""

import os
import re
import secrets
import uuid
from datetime import datetime

from .db import transaction

PAYMENT_METHODS = ("card", "click", "payme", "cash")
MAX_SEATS_PER_BOOKING = 10
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# A seat is taken if it belongs to a paid booking or to an unpaid hold that has not expired.
TAKEN_SEATS_SQL = """
    SELECT bs.seat_id
    FROM booking_seats bs
    JOIN bookings b ON b.id = bs.booking_id
    WHERE b.status = 'paid'
       OR (b.status = 'pending' AND b.expires_at > now())
"""


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def hold_minutes():
    return int(os.environ.get("HOLD_MINUTES", "10"))


# ---------------------------------------------------------------- events & seats

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
        cur.executemany(
            "INSERT INTO seats (event_id, label, price) VALUES (%s, %s, %s)", seats
        )
    return get_event(event_id)


def list_events():
    with transaction() as cur:
        cur.execute(
            f"""
            SELECT e.id, e.title, e.venue, e.starts_at,
                   count(s.id) AS total_seats,
                   count(s.id) FILTER (WHERE s.id NOT IN ({TAKEN_SEATS_SQL})) AS available_seats
            FROM events e
            LEFT JOIN seats s ON s.event_id = e.id
            GROUP BY e.id
            ORDER BY e.starts_at
            """
        )
        return cur.fetchall()


def get_event(event_id):
    for event in list_events():
        if event["id"] == event_id:
            return event
    raise ApiError(404, "event not found")


def list_seats(event_id):
    get_event(event_id)
    with transaction() as cur:
        cur.execute(
            f"""
            SELECT s.id, s.label, s.price, (s.id NOT IN ({TAKEN_SEATS_SQL})) AS available
            FROM seats s
            WHERE s.event_id = %s
            ORDER BY s.id
            """,
            (event_id,),
        )
        return cur.fetchall()


# ---------------------------------------------------------------- bookings

def create_booking(data):
    event_id = data.get("event_id")
    seat_ids = data.get("seat_ids")
    name = (data.get("customer_name") or "").strip()
    email = (data.get("customer_email") or "").strip().lower()

    if not isinstance(event_id, int):
        raise ApiError(400, "event_id must be an integer")
    if (
        not isinstance(seat_ids, list)
        or not seat_ids
        or not all(isinstance(s, int) for s in seat_ids)
    ):
        raise ApiError(400, "seat_ids must be a non-empty list of integers")
    if len(set(seat_ids)) != len(seat_ids):
        raise ApiError(400, "seat_ids contains duplicates")
    if len(seat_ids) > MAX_SEATS_PER_BOOKING:
        raise ApiError(400, f"at most {MAX_SEATS_PER_BOOKING} seats per booking")
    if not name:
        raise ApiError(400, "customer_name is required")
    if not EMAIL_RE.match(email):
        raise ApiError(400, "customer_email is not a valid email")

    with transaction() as cur:
        # Lock the requested seats; a parallel booking for the same seats waits here.
        cur.execute(
            "SELECT id, label, price FROM seats WHERE event_id = %s AND id = ANY(%s) "
            "ORDER BY id FOR UPDATE",
            (event_id, seat_ids),
        )
        seats = cur.fetchall()
        if len(seats) != len(seat_ids):
            raise ApiError(404, "one or more seats do not exist for this event")

        cur.execute(
            f"SELECT s.label FROM seats s WHERE s.id = ANY(%s) AND s.id IN ({TAKEN_SEATS_SQL})",
            (seat_ids,),
        )
        taken = [r["label"] for r in cur.fetchall()]
        if taken:
            raise ApiError(409, f"seats already taken: {', '.join(sorted(taken))}")

        total = sum(s["price"] for s in seats)
        cur.execute(
            """
            INSERT INTO bookings (event_id, customer_name, customer_email, total, expires_at)
            VALUES (%s, %s, %s, %s, now() + make_interval(mins => %s))
            RETURNING id
            """,
            (event_id, name, email, total, hold_minutes()),
        )
        booking_id = cur.fetchone()["id"]
        cur.executemany(
            "INSERT INTO booking_seats (booking_id, seat_id) VALUES (%s, %s)",
            [(booking_id, s["id"]) for s in seats],
        )
    return get_booking(booking_id)


def _expire_if_needed(cur, booking_id):
    cur.execute(
        "UPDATE bookings SET status = 'expired' "
        "WHERE id = %s AND status = 'pending' AND expires_at <= now()",
        (booking_id,),
    )


def get_booking(booking_id):
    with transaction() as cur:
        _expire_if_needed(cur, booking_id)
        cur.execute(
            "SELECT id, event_id, customer_name, customer_email, status, total, "
            "expires_at, created_at FROM bookings WHERE id = %s",
            (booking_id,),
        )
        booking = cur.fetchone()
        if not booking:
            raise ApiError(404, "booking not found")
        cur.execute(
            "SELECT s.id, s.label, s.price FROM booking_seats bs "
            "JOIN seats s ON s.id = bs.seat_id WHERE bs.booking_id = %s ORDER BY s.id",
            (booking_id,),
        )
        booking["seats"] = cur.fetchall()
        cur.execute(
            "SELECT t.code, s.label AS seat FROM tickets t JOIN seats s ON s.id = t.seat_id "
            "WHERE t.booking_id = %s ORDER BY s.id",
            (booking_id,),
        )
        booking["tickets"] = cur.fetchall()
        cur.execute(
            "SELECT amount, method, status, reference, created_at FROM payments "
            "WHERE booking_id = %s",
            (booking_id,),
        )
        booking["payment"] = cur.fetchone()
    return booking


def cancel_booking(booking_id):
    with transaction() as cur:
        _expire_if_needed(cur, booking_id)
        cur.execute("SELECT status FROM bookings WHERE id = %s FOR UPDATE", (booking_id,))
        row = cur.fetchone()
        if not row:
            raise ApiError(404, "booking not found")
        if row["status"] != "pending":
            raise ApiError(409, f"only pending bookings can be cancelled (status: {row['status']})")
        cur.execute("UPDATE bookings SET status = 'cancelled' WHERE id = %s", (booking_id,))
    return get_booking(booking_id)


# ---------------------------------------------------------------- payments & tickets

def _ticket_code():
    raw = secrets.token_hex(4).upper()
    return f"TKT-{raw[:4]}-{raw[4:]}"


def pay_booking(booking_id, data):
    """Simulated payment provider: no real card data is ever accepted or stored."""
    method = (data.get("method") or "").strip().lower()
    if method not in PAYMENT_METHODS:
        raise ApiError(400, f"method must be one of: {', '.join(PAYMENT_METHODS)}")

    with transaction() as cur:
        _expire_if_needed(cur, booking_id)
        cur.execute(
            "SELECT id, status, total FROM bookings WHERE id = %s FOR UPDATE", (booking_id,)
        )
        booking = cur.fetchone()
        if not booking:
            raise ApiError(404, "booking not found")
        if booking["status"] == "paid":
            raise ApiError(409, "booking is already paid")
        if booking["status"] != "pending":
            raise ApiError(409, f"booking cannot be paid (status: {booking['status']})")

        cur.execute(
            "INSERT INTO payments (booking_id, amount, method, status, reference) "
            "VALUES (%s, %s, %s, 'succeeded', %s)",
            (booking_id, booking["total"], method, f"PAY-{uuid.uuid4().hex[:12].upper()}"),
        )
        cur.execute("UPDATE bookings SET status = 'paid' WHERE id = %s", (booking_id,))
        cur.execute("SELECT seat_id FROM booking_seats WHERE booking_id = %s", (booking_id,))
        cur.executemany(
            "INSERT INTO tickets (code, booking_id, seat_id) VALUES (%s, %s, %s)",
            [(_ticket_code(), booking_id, r["seat_id"]) for r in cur.fetchall()],
        )
    return get_booking(booking_id)


def get_ticket(code):
    with transaction() as cur:
        cur.execute(
            """
            SELECT t.code, t.issued_at, s.label AS seat, e.title AS event, e.venue,
                   e.starts_at, b.customer_name
            FROM tickets t
            JOIN seats s    ON s.id = t.seat_id
            JOIN events e   ON e.id = s.event_id
            JOIN bookings b ON b.id = t.booking_id
            WHERE t.code = %s
            """,
            (code.upper(),),
        )
        ticket = cur.fetchone()
    if not ticket:
        raise ApiError(404, "ticket not found")
    return ticket


# ---------------------------------------------------------------- demo data

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

"""Bookings: holding seats for a customer until they pay, cancel, or the hold expires.

The key rule: a seat can never be held or sold twice.
  1. Before checking a seat, the booking takes a Postgres advisory lock for that seat id
     (pg_advisory_xact_lock). Two people clicking the same seat at the same moment are handled
     one after the other, even with many booking-service replicas, because the lock lives in
     the database.
  2. ticket-service has UNIQUE(seat_id), so even a bug cannot issue two tickets for one seat.
"""

import os
import re

from common.db import transaction
from common.errors import ApiError

from . import clients

MAX_SEATS_PER_BOOKING = 10
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SEAT_LOCK_NAMESPACE = 7  # first key of the two-key advisory lock: (namespace, seat_id)

# A seat is taken if it belongs to a paid booking or to an unpaid hold that has not expired.
TAKEN_SEATS_SQL = """
    SELECT bs.seat_id
    FROM booking_seats bs
    JOIN bookings b ON b.id = bs.booking_id
    WHERE b.status = 'paid'
       OR (b.status = 'pending' AND b.expires_at > now())
"""


def hold_minutes():
    return int(os.environ.get("HOLD_MINUTES", "10"))


def availability(event_id):
    """Seat map of an event with an `available` flag (catalog from event-service)."""
    seats = clients.event_seats(event_id)
    ids = [s["id"] for s in seats]
    with transaction() as cur:
        cur.execute(
            f"SELECT seat_id FROM ({TAKEN_SEATS_SQL}) t WHERE seat_id = ANY(%s)", (ids,)
        )
        taken = {r["seat_id"] for r in cur.fetchall()}
    return {
        "event_id": event_id,
        "total_seats": len(seats),
        "available_seats": len(seats) - len(taken),
        "seats": [{**s, "available": s["id"] not in taken} for s in seats],
    }


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

    # Ask event-service which of these seats exist for this event (and their price).
    seats = clients.lookup_seats(event_id, seat_ids)
    if len(seats) != len(seat_ids):
        raise ApiError(404, "one or more seats do not exist for this event")

    with transaction() as cur:
        # Lock the seats in a fixed order (no deadlocks); a parallel booking waits here.
        for seat_id in sorted(seat_ids):
            cur.execute("SELECT pg_advisory_xact_lock(%s, %s)", (SEAT_LOCK_NAMESPACE, seat_id))

        cur.execute(
            f"SELECT seat_id FROM ({TAKEN_SEATS_SQL}) t WHERE seat_id = ANY(%s)", (seat_ids,)
        )
        taken_ids = {r["seat_id"] for r in cur.fetchall()}
        if taken_ids:
            labels = sorted(s["label"] for s in seats if s["id"] in taken_ids)
            raise ApiError(409, f"seats already taken: {', '.join(labels)}")

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
            "INSERT INTO booking_seats (booking_id, seat_id, label, price) VALUES (%s, %s, %s, %s)",
            [(booking_id, s["id"], s["label"], s["price"]) for s in seats],
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
            "SELECT seat_id AS id, label, price FROM booking_seats "
            "WHERE booking_id = %s ORDER BY seat_id",
            (booking_id,),
        )
        booking["seats"] = cur.fetchall()
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


def mark_paid(booking_id):
    """Internal (called by payment-service). Idempotent: calling it twice is safe."""
    with transaction() as cur:
        _expire_if_needed(cur, booking_id)
        cur.execute("SELECT status FROM bookings WHERE id = %s FOR UPDATE", (booking_id,))
        row = cur.fetchone()
        if not row:
            raise ApiError(404, "booking not found")
        if row["status"] == "pending":
            cur.execute("UPDATE bookings SET status = 'paid' WHERE id = %s", (booking_id,))
        elif row["status"] != "paid":
            raise ApiError(409, f"booking cannot be paid (status: {row['status']})")
    return get_booking(booking_id)

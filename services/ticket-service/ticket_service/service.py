"""Tickets: issued once per booking, one per seat, checked at the entrance."""

import secrets

import psycopg2

from common.db import transaction
from common.errors import ApiError

from . import clients

BOOKING_LOCK_NAMESPACE = 11

TICKET_SQL = """
    SELECT code, issued_at, seat_label AS seat, event_title AS event, venue, starts_at,
           customer_name, booking_id
    FROM tickets
"""


def _ticket_code():
    raw = secrets.token_hex(4).upper()
    return f"TKT-{raw[:4]}-{raw[4:]}"


def _short(rows):
    return [{"code": r["code"], "seat": r["seat"]} for r in rows]


def issue_tickets(data):
    """Internal (called by payment-service). Idempotent: a second call returns the same tickets."""
    booking_id = data.get("booking_id")
    event_id = data.get("event_id")
    customer = (data.get("customer_name") or "").strip()
    seats = data.get("seats")
    if not isinstance(booking_id, int) or not isinstance(event_id, int) or not customer:
        raise ApiError(400, "booking_id, event_id and customer_name are required")
    if not isinstance(seats, list) or not seats:
        raise ApiError(400, "seats must be a non-empty list")

    event = clients.get_event(event_id)

    with transaction() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(%s, %s)", (BOOKING_LOCK_NAMESPACE, booking_id))
        cur.execute(TICKET_SQL + " WHERE booking_id = %s ORDER BY seat_id", (booking_id,))
        existing = cur.fetchall()
        if existing:
            return False, _short(existing)
        try:
            cur.executemany(
                "INSERT INTO tickets (code, booking_id, event_id, seat_id, seat_label, "
                "event_title, venue, starts_at, customer_name) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                [
                    (
                        _ticket_code(), booking_id, event_id, s["seat_id"], s["label"],
                        event["title"], event["venue"], event["starts_at"], customer,
                    )
                    for s in sorted(seats, key=lambda s: s["seat_id"])
                ],
            )
        except psycopg2.errors.UniqueViolation:
            raise ApiError(409, "a ticket for one of these seats already exists") from None
        cur.execute(TICKET_SQL + " WHERE booking_id = %s ORDER BY seat_id", (booking_id,))
        return True, _short(cur.fetchall())


def stats():
    """Numbers for the dashboard. No ticket codes: they are entry passes."""
    with transaction() as cur:
        cur.execute(
            "SELECT count(*) AS tickets, "
            "count(*) FILTER (WHERE issued_at >= date_trunc('day', now())) AS issued_today "
            "FROM tickets"
        )
        row = cur.fetchone()
        cur.execute(
            "SELECT event_title AS event, count(*) AS tickets FROM tickets "
            "GROUP BY event_title ORDER BY tickets DESC, event_title LIMIT 5"
        )
        row["top_events"] = cur.fetchall()
    return row


def get_ticket(code):
    with transaction() as cur:
        cur.execute(TICKET_SQL + " WHERE code = %s", (code.upper(),))
        ticket = cur.fetchone()
    if not ticket:
        raise ApiError(404, "ticket not found")
    return ticket


def tickets_for_booking(booking_id):
    with transaction() as cur:
        cur.execute(TICKET_SQL + " WHERE booking_id = %s ORDER BY seat_id", (booking_id,))
        return cur.fetchall()

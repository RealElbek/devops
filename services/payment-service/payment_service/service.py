"""Payments (simulated provider: no real card data is ever accepted or stored).

Paying touches three services, so there is no single database transaction. Instead every step
is safe to repeat (idempotent), and the payment row remembers how far we got:

  1. payment row created as 'pending'               (payment-service DB, row locked)
  2. booking-service marks the booking 'paid'       (idempotent: twice is fine)
     -> if the booking expired / was cancelled: payment becomes 'failed', 409
  3. payment becomes 'succeeded'
  4. ticket-service issues tickets                  (idempotent per booking)

If a service is down in the middle, the client gets 503 and can simply call /pay again:
the flow continues from where it stopped and never charges or issues twice.
"""

import uuid

from common.db import transaction
from common.errors import ApiError

from . import clients

PAYMENT_METHODS = ("card", "click", "payme", "cash")

PAYMENT_FIELDS = "booking_id, amount, method, status, reference, created_at, updated_at"


def get_payment(booking_id):
    with transaction() as cur:
        cur.execute(f"SELECT {PAYMENT_FIELDS} FROM payments WHERE booking_id = %s", (booking_id,))
        payment = cur.fetchone()
    if not payment:
        raise ApiError(404, "payment not found")
    return payment


def pay_booking(booking_id, data):
    method = (data.get("method") or "").strip().lower()
    if method not in PAYMENT_METHODS:
        raise ApiError(400, f"method must be one of: {', '.join(PAYMENT_METHODS)}")

    booking = clients.get_booking(booking_id)  # 404 if it does not exist
    if booking["status"] not in ("pending", "paid"):
        raise ApiError(409, f"booking cannot be paid (status: {booking['status']})")

    failure = None
    with transaction() as cur:
        cur.execute(
            "INSERT INTO payments (booking_id, amount, method, status, reference) "
            "VALUES (%s, %s, %s, 'pending', %s) ON CONFLICT (booking_id) DO NOTHING",
            (booking_id, booking["total"], method, f"PAY-{uuid.uuid4().hex[:12].upper()}"),
        )
        # Row lock: two /pay calls for the same booking run one after the other.
        cur.execute("SELECT status FROM payments WHERE booking_id = %s FOR UPDATE", (booking_id,))
        already_paid = cur.fetchone()["status"] == "succeeded"

        if not already_paid:
            try:
                clients.mark_paid(booking_id)
            except ApiError as e:
                if e.status != 409:
                    raise  # service down: roll back, the client can retry
                failure = e.message
            new_status = "failed" if failure else "succeeded"
            cur.execute(
                "UPDATE payments SET status = %s, method = %s, updated_at = now() "
                "WHERE booking_id = %s",
                (new_status, method, booking_id),
            )
    if failure:
        raise ApiError(409, failure)

    result = clients.issue_tickets(booking)
    if already_paid and not result["created"]:
        raise ApiError(409, "booking is already paid")
    return {
        "booking_id": booking_id,
        "status": "paid",
        "total": booking["total"],
        "payment": get_payment(booking_id),
        "tickets": result["tickets"],
    }

"""Calls from payment-service to other services."""

import os

from common.http import call


def _booking_url():
    return os.environ.get("BOOKING_SERVICE_URL", "http://booking-service:5000")


def _ticket_url():
    return os.environ.get("TICKET_SERVICE_URL", "http://ticket-service:5000")


def get_booking(booking_id):
    return call("booking-service", "GET", f"{_booking_url()}/api/v1/bookings/{booking_id}")


def mark_paid(booking_id):
    return call(
        "booking-service", "POST", f"{_booking_url()}/internal/bookings/{booking_id}/mark-paid"
    )


def issue_tickets(booking):
    """Ask ticket-service for tickets. Idempotent: returns {"created": bool, "tickets": [...]}."""
    return call(
        "ticket-service",
        "POST",
        f"{_ticket_url()}/internal/tickets",
        json={
            "booking_id": booking["id"],
            "event_id": booking["event_id"],
            "customer_name": booking["customer_name"],
            "seats": [{"seat_id": s["id"], "label": s["label"]} for s in booking["seats"]],
        },
    )

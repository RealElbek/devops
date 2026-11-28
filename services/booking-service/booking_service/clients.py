"""Calls from booking-service to other services."""

import os

from common.http import call


def _event_url():
    return os.environ.get("EVENT_SERVICE_URL", "http://event-service:5000")


def event_seats(event_id):
    """All seats of an event (404 if the event does not exist)."""
    return call("event-service", "GET", f"{_event_url()}/api/v1/events/{event_id}/seats")


def lookup_seats(event_id, seat_ids):
    """Only the requested seats that really belong to this event."""
    return call(
        "event-service",
        "POST",
        f"{_event_url()}/internal/seats/lookup",
        json={"event_id": event_id, "seat_ids": seat_ids},
    )

"""Calls from ticket-service to other services."""

import os

from common.http import call


def get_event(event_id):
    url = os.environ.get("EVENT_SERVICE_URL", "http://event-service:5000")
    return call("event-service", "GET", f"{url}/api/v1/events/{event_id}")

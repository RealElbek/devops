"""event-service: events and seat maps."""

import os
from pathlib import Path

from flask import jsonify

from common.web import create_service_app, json_body

from . import service

API = "/api/v1"


def register_routes(app):
    @app.get(f"{API}/events")
    def events():
        return jsonify(service.list_events())

    @app.post(f"{API}/events")
    def create_event():
        return jsonify(service.create_event(json_body())), 201

    @app.get(f"{API}/events/<int:event_id>")
    def event(event_id):
        return jsonify(service.get_event(event_id))

    @app.get(f"{API}/events/<int:event_id>/seats")
    def seats(event_id):
        return jsonify(service.list_seats(event_id))

    @app.get(f"{API}/stats")
    def stats():
        return jsonify(service.stats())

    # internal: only other services call this (the gateway does not route /internal)
    @app.post("/internal/seats/lookup")
    def lookup_seats():
        return jsonify(service.lookup_seats(json_body()))


def _seed():
    if os.environ.get("SEED_DEMO", "true").lower() == "true":
        service.seed_demo()


def create_app():
    return create_service_app(
        "event-service", Path(__file__).with_name("schema.sql"), register_routes, on_start=_seed
    )

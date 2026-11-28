"""ticket-service: issues tickets and checks them at the entrance."""

from pathlib import Path

from flask import jsonify, request

from common.errors import ApiError
from common.web import create_service_app, json_body

from . import service

API = "/api/v1"


def register_routes(app):
    @app.get(f"{API}/stats")
    def stats():
        return jsonify(service.stats())

    @app.get(f"{API}/tickets/<code>")
    def ticket(code):
        return jsonify(service.get_ticket(code))

    @app.get(f"{API}/tickets")
    def tickets():
        booking_id = request.args.get("booking_id", type=int)
        if booking_id is None:
            raise ApiError(400, "booking_id query parameter is required")
        return jsonify(service.tickets_for_booking(booking_id))

    # internal: only payment-service calls this (the gateway does not route /internal)
    @app.post("/internal/tickets")
    def issue():
        created, tickets = service.issue_tickets(json_body())
        return jsonify(created=created, tickets=tickets), 201 if created else 200


def create_app():
    return create_service_app(
        "ticket-service", Path(__file__).with_name("schema.sql"), register_routes
    )

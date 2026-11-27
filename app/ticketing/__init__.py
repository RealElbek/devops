"""Ticket booking service (events, seats, bookings, payments, tickets)."""

import logging
import os
import socket

from flask import Flask, jsonify, request

from . import db, service
from .service import ApiError

API = "/api/v1"


def _json_body():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "request body must be a JSON object")
    return body


def create_app():
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app = Flask(__name__)
    app.json.sort_keys = False

    db.init_schema()
    if os.environ.get("SEED_DEMO", "true").lower() == "true":
        service.seed_demo()

    @app.errorhandler(ApiError)
    def api_error(e):
        return jsonify(error=e.message), e.status

    @app.errorhandler(404)
    def not_found(_):
        return jsonify(error="not found"), 404

    @app.errorhandler(405)
    def method_not_allowed(_):
        return jsonify(error="method not allowed"), 405

    @app.get("/")
    def index():
        return jsonify(
            service="ticket-booking",
            served_by=socket.gethostname(),
            endpoints={
                "events": f"{API}/events",
                "seats": f"{API}/events/<id>/seats",
                "book": f"POST {API}/bookings",
                "pay": f"POST {API}/bookings/<id>/pay",
                "ticket": f"{API}/tickets/<code>",
            },
        )

    @app.get("/health")
    def health():
        try:
            db.ping()
            return jsonify(status="ok", db="ok", served_by=socket.gethostname())
        except Exception as e:  # any DB failure means "not healthy"
            return jsonify(status="error", db=str(e).strip(), served_by=socket.gethostname()), 503

    # events & seats
    @app.get(f"{API}/events")
    def events():
        return jsonify(service.list_events())

    @app.post(f"{API}/events")
    def create_event():
        return jsonify(service.create_event(_json_body())), 201

    @app.get(f"{API}/events/<int:event_id>")
    def event(event_id):
        return jsonify(service.get_event(event_id))

    @app.get(f"{API}/events/<int:event_id>/seats")
    def seats(event_id):
        return jsonify(service.list_seats(event_id))

    # bookings & payments
    @app.post(f"{API}/bookings")
    def create_booking():
        return jsonify(service.create_booking(_json_body())), 201

    @app.get(f"{API}/bookings/<int:booking_id>")
    def booking(booking_id):
        return jsonify(service.get_booking(booking_id))

    @app.post(f"{API}/bookings/<int:booking_id>/pay")
    def pay(booking_id):
        return jsonify(service.pay_booking(booking_id, _json_body()))

    @app.post(f"{API}/bookings/<int:booking_id>/cancel")
    def cancel(booking_id):
        return jsonify(service.cancel_booking(booking_id))

    # tickets
    @app.get(f"{API}/tickets/<code>")
    def ticket(code):
        return jsonify(service.get_ticket(code))

    return app

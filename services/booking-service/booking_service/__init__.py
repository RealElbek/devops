"""booking-service: seat holds, bookings, availability."""

from pathlib import Path

from flask import jsonify

from common.web import create_service_app, json_body

from . import service

API = "/api/v1"


def register_routes(app):
    @app.get(f"{API}/events/<int:event_id>/availability")
    def availability(event_id):
        return jsonify(service.availability(event_id))

    @app.post(f"{API}/bookings")
    def create_booking():
        return jsonify(service.create_booking(json_body())), 201

    @app.get(f"{API}/bookings/<int:booking_id>")
    def booking(booking_id):
        return jsonify(service.get_booking(booking_id))

    @app.post(f"{API}/bookings/<int:booking_id>/cancel")
    def cancel(booking_id):
        return jsonify(service.cancel_booking(booking_id))

    # internal: only payment-service calls this (the gateway does not route /internal)
    @app.post("/internal/bookings/<int:booking_id>/mark-paid")
    def mark_paid(booking_id):
        return jsonify(service.mark_paid(booking_id))


def create_app():
    return create_service_app(
        "booking-service", Path(__file__).with_name("schema.sql"), register_routes
    )

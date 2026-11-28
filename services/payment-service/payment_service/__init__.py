"""payment-service: simulated payments; triggers booking confirmation and ticket issuing."""

from pathlib import Path

from flask import jsonify

from common.web import create_service_app, json_body

from . import service

API = "/api/v1"


def register_routes(app):
    @app.post(f"{API}/bookings/<int:booking_id>/pay")
    def pay(booking_id):
        return jsonify(service.pay_booking(booking_id, json_body()))

    @app.get(f"{API}/payments/<int:booking_id>")
    def payment(booking_id):
        return jsonify(service.get_payment(booking_id))


def create_app():
    return create_service_app(
        "payment-service", Path(__file__).with_name("schema.sql"), register_routes
    )

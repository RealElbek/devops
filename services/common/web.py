"""Flask setup shared by all services: logging, JSON errors and the /health endpoint."""

import logging
import os
import socket

from flask import Flask, jsonify, request

from . import db
from .errors import ApiError


def json_body():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "request body must be a JSON object")
    return body


def create_service_app(name, schema_file, register_routes, on_start=None):
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format=f"%(asctime)s %(levelname)s {name} %(name)s: %(message)s",
    )
    app = Flask(name)
    app.json.sort_keys = False

    db.init_schema(schema_file)
    if on_start:
        on_start()

    @app.errorhandler(ApiError)
    def api_error(e):
        return jsonify(error=e.message), e.status

    @app.errorhandler(404)
    def not_found(_):
        return jsonify(error="not found"), 404

    @app.errorhandler(405)
    def method_not_allowed(_):
        return jsonify(error="method not allowed"), 405

    @app.get("/health")
    def health():
        info = {"service": name, "served_by": socket.gethostname()}
        try:
            db.ping()
            return jsonify(status="ok", db="ok", **info)
        except Exception as e:  # any DB failure means "not healthy"
            return jsonify(status="error", db=str(e).strip(), **info), 503

    register_routes(app)
    return app

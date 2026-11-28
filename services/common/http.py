"""Service-to-service HTTP calls.

- Short timeouts: a slow service must not hang the caller.
- The caller's X-Request-ID is forwarded, so one request can be followed through every log.
- Network errors and 5xx answers become 503 "<service> unavailable"; 4xx answers are passed on.
"""

import requests
from flask import has_request_context, request

from .errors import ApiError

TIMEOUT = (2, 5)  # seconds: connect, read


def call(service, method, url, json=None):
    headers = {}
    if has_request_context() and request.headers.get("X-Request-ID"):
        headers["X-Request-ID"] = request.headers["X-Request-ID"]
    try:
        res = requests.request(method, url, json=json, headers=headers, timeout=TIMEOUT)
    except requests.RequestException:
        raise ApiError(503, f"{service} unavailable") from None
    if res.status_code >= 500:
        raise ApiError(503, f"{service} unavailable")
    try:
        body = res.json()
    except ValueError:
        raise ApiError(502, f"{service} returned an invalid response") from None
    if res.status_code >= 400:
        raise ApiError(res.status_code, body.get("error", f"{service} error"))
    return body

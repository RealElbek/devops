"""Small shared library used by every microservice (DB helpers, errors, HTTP client, app setup).

It is copied into each service image at build time. It holds no business logic: every service
owns its own data and rules.
"""

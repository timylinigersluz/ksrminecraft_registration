from __future__ import annotations

from flask import request

from main import application


_ALLOWED_ORIGINS = {
    "https://ksrminecraft.ch",
    "https://www.ksrminecraft.ch",
    "http://127.0.0.1:5000",
    "http://localhost:5000",
}


@application.after_request
def add_cors_headers(resp):
    """Restore the CORS behaviour used by the working Unraid production app."""
    origin = request.headers.get("Origin")

    if origin in _ALLOWED_ORIGINS:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Vary"] = "Origin"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, Accept, X-Requested-With"
        )
        resp.headers["Access-Control-Max-Age"] = "86400"

    return resp

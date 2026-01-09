# app/routes/registration_routes.py

from __future__ import annotations

from flask import Blueprint, current_app, render_template, request, redirect, url_for

from app.services.registration_service import process_registration


registration_bp = Blueprint("registration", __name__)


@registration_bp.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@registration_bp.route("/success", methods=["GET"])
def success():
    cfg = current_app.config["APP_CONFIG"]
    return render_template("success.html", config=cfg)


@registration_bp.route("/registration_completed", methods=["GET"])
def registration_completed():
    cfg = current_app.config["APP_CONFIG"]
    return render_template("registration_completed.html", config=cfg)


@registration_bp.route("/error", methods=["GET"])
def error():
    # Optional: wenn du error.html weiterhin auch über Queryparam nutzen willst
    errors = request.args.get("errors")
    return render_template("error.html", errors=errors)


@registration_bp.route("/register", methods=["GET"])
def show_registration_form():
    return render_template("registration.html")


@registration_bp.route("/register", methods=["POST"])
def register():
    cfg = current_app.config["APP_CONFIG"]
    serializer = current_app.config["SERIALIZER"]

    result = process_registration(
        form=request.form,
        config=cfg,
        serializer=serializer,
        request_host_url=request.host_url,
    )

    if not result.get("ok"):
        return render_template("error.html", errors=result.get("errors", ["Unbekannter Fehler."]))

    return redirect(url_for("registration.success"))

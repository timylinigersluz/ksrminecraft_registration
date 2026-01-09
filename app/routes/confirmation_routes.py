# app/routes/confirmation_routes.py

from __future__ import annotations

from flask import Blueprint, current_app, render_template, request, redirect, url_for

from app.services.confirmation_service import (
    decode_confirmation_token,
    confirm_registration_by_token,
)


confirmation_bp = Blueprint("confirmation", __name__)


@confirmation_bp.route("/confirm_page/<token>", methods=["GET"])
def confirm_page(token: str):
    cfg = current_app.config["APP_CONFIG"]
    serializer = current_app.config["SERIALIZER"]

    decoded = decode_confirmation_token(token=token, serializer=serializer, config=cfg)
    if not decoded.get("ok"):
        return render_template("error.html", errors=[decoded.get("error", "Unbekannter Fehler.")])

    return render_template("confirm_page.html", email=decoded["email"], token=token)


@confirmation_bp.route("/confirm", methods=["POST"])
def confirm_email():
    cfg = current_app.config["APP_CONFIG"]
    serializer = current_app.config["SERIALIZER"]

    token = request.form.get("token")
    if not token:
        return render_template("error.html", errors=["Fehlender Token."])

    result = confirm_registration_by_token(token=token, serializer=serializer, config=cfg)
    if not result.get("ok"):
        return render_template("error.html", errors=[result.get("error", "Unbekannter Fehler.")])

    # erfolgreicher Confirm -> auf Abschlussseite
    return redirect(url_for("registration.registration_completed"))

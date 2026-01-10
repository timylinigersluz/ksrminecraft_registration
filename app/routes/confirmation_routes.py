# app/routes/confirmation_routes.py

from flask import Blueprint, current_app, render_template, request

from app.services.confirmation_service import decode_confirmation_token, confirm_registration_by_token
from app.infrastructure.database_handler import DatabaseHandler

confirmation_bp = Blueprint("confirmation", __name__)


def _get_client_ip() -> str:
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    xrip = request.headers.get("X-Real-IP")
    if xrip:
        return xrip.strip()
    return (request.remote_addr or "unknown").strip()


@confirmation_bp.route("/confirm_page/<token>", methods=["GET"])
def confirm_page(token):
    cfg = current_app.config["APP_CONFIG"]
    serializer = current_app.config["SERIALIZER"]

    decoded = decode_confirmation_token(token=token, serializer=serializer, config=cfg)
    if not decoded.get("ok"):
        return render_template("error.html", errors=[decoded.get("error", "Ungültiger Link.")]), 400

    email = decoded["email"]

    # WICHTIG: Confirm-Page nur anzeigen, wenn es wirklich noch einen unbestätigten Eintrag gibt
    with DatabaseHandler(cfg) as db:
        if not db.has_unconfirmed_registration(email):
            return render_template(
                "error.html",
                errors=["Registrierung nicht gefunden oder bereits bestätigt."],
            ), 400

        firstname = db.get_latest_firstname(email) or "Spieler"

    return render_template(
        "confirm_page.html",
        token=token,
        email=email,
        firstname=firstname,
        config=cfg,
    )


@confirmation_bp.route("/confirm_email", methods=["POST"])
def confirm_email():
    cfg = current_app.config["APP_CONFIG"]
    serializer = current_app.config["SERIALIZER"]
    token = request.form.get("token", "")

    result = confirm_registration_by_token(
        token=token,
        serializer=serializer,
        config=cfg,
        client_ip=_get_client_ip(),
    )

    if not result.get("ok"):
        return render_template("error.html", errors=[result.get("error", "Unbekannter Fehler.")]), 400

    # Optional: du könntest hier minecraft_username/whitelisted ins Template geben,
    # falls du es anzeigen willst. Aktuell belasse ich es wie bei dir.
    return render_template("registration_completed.html", config=cfg)

from __future__ import annotations

import datetime

from flask import jsonify, redirect, render_template, request, url_for

import main as legacy


application = legacy.application

_ALLOWED_ORIGINS = {
    "https://ksrminecraft.ch",
    "https://www.ksrminecraft.ch",
    "http://127.0.0.1:5000",
    "http://localhost:5000",
}


def _wants_json_response() -> bool:
    """Mirror the JSON detection used by the working Unraid production app."""
    xrw = (request.headers.get("X-Requested-With") or "").lower()
    if xrw == "fetch":
        return True

    accept = (request.headers.get("Accept") or "").lower()
    return "application/json" in accept


def _json_error(errors: list[str]):
    return (
        jsonify(
            ok=False,
            errors=errors,
            message=" | ".join(errors),
        ),
        400,
    )


_original_register = application.view_functions["register"]


def _register_with_json_compat():
    """Keep the legacy HTML flow, but restore JSON for embedded fetch requests."""
    if not _wants_json_response():
        return _original_register()

    legacy.logger.info("Versuche neuen User zu registrieren.")

    firstname = (request.form.get("firstname") or "").strip()
    lastname = (request.form.get("lastname") or "").strip()
    email = (request.form.get("email") or "").strip()
    school = (request.form.get("school") or "").strip()
    minecraft_username = (request.form.get("minecraft_username") or "").strip()

    errors = []
    if not firstname:
        errors.append("Vorname ist erforderlich.")
    if not lastname:
        errors.append("Nachname ist erforderlich.")
    if not email:
        errors.append("E-Mail ist erforderlich.")
    if not school:
        errors.append("Schule ist erforderlich.")
    if not minecraft_username:
        errors.append("Minecraft-Benutzername ist erforderlich.")

    if errors:
        return _json_error(errors)

    if not legacy.is_email_allowed(email, legacy.config):
        accepted_mail_endings = legacy.config.get("accepted_mail_endings", []) or []
        legacy.logger.info(
            "Abbruch: Unzulässige Mailadresse (nicht in Whitelist und Endung nicht erlaubt)."
        )
        return _json_error(
            [
                "Die Registrierung ist nur für E-Mail-Adressen mit folgenden Endungen erlaubt: "
                + ", ".join(accepted_mail_endings)
            ]
        )

    with legacy.DatabaseHandler(legacy.config) as db:
        count = db.get_user_count_by_email(email)

    max_permitted = legacy.get_max_users_per_mail(email, legacy.config)
    if count >= max_permitted:
        legacy.logger.info(
            f"Abbruch: Zu viele User mit dieser E-Mail-Adresse registriert ({email})"
        )
        return _json_error(
            [f"Es sind bereits {max_permitted} Benutzer mit dieser E-Mail-Adresse registriert."]
        )

    with legacy.DatabaseHandler(legacy.config) as db:
        if db.is_username_exists(minecraft_username):
            legacy.logger.info(
                f"Abbruch: Benutzername bereits in der Datenbank vorhanden ({minecraft_username})."
            )
            return _json_error(["Dieser Minecraft-Benutzername ist bereits registriert."])

    if not legacy.mojang_handler.is_official_username(minecraft_username):
        legacy.logger.info(
            f"Abbruch: Kein gültiger Minecraft-Account ({minecraft_username})."
        )
        return _json_error(["Ungültiger Minecraft-Benutzername."])

    legacy.logger.info("Generiere Token für Bestätigungslink.")
    token = legacy.serializer.dumps(email, salt="email-confirm")

    legacy.logger.info("Speichere Registrierungsdaten in Datenbank.")
    created_at = datetime.datetime.now()
    with legacy.DatabaseHandler(legacy.config) as db:
        db.insert_registration(
            firstname,
            lastname,
            email,
            school,
            minecraft_username,
            0,
            created_at,
        )

    confirmation_link = request.host_url + "confirm_page/" + token
    legacy.logger.info(f"Sende Bestätigungslink mit Token ({token}) per E-Mail.")
    legacy.mail_handler.send_confirmation_email(
        to_email=email,
        confirmation_link=confirmation_link,
        firstname=firstname,
    )

    legacy.logger.info("Registrierung erfolgreich abgeschlossen.")
    redirect_url = url_for(
        "success",
        email=email,
        firstname=firstname,
        _external=True,
    )
    return (
        jsonify(
            ok=True,
            message="Erfolgreich gesendet.\nPrüfe in 2 Minuten dein Postfach (auch Spam).",
            redirect_url=redirect_url,
        ),
        200,
    )


application.view_functions["register"] = _register_with_json_compat


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

# app/services/registration_service.py

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional

from app.infrastructure.log_handler import logger
from app.infrastructure.database_handler import DatabaseHandler
from app.infrastructure import mail_handler
from app.infrastructure import mojang_handler

from app.policies.email_policy import is_email_allowed, get_max_users_per_mail


def _get_form_value(form: Any, key: str) -> str:
    """
    Helfer: kompatibel mit Flask request.form (MultiDict) und normalen dicts.
    """
    try:
        return (form.get(key) or "").strip()
    except Exception:
        return ""


def validate_registration_form(form: Any) -> List[str]:
    """
    Validiert Pflichtfelder aus dem Formular und liefert eine Fehlerliste.
    """
    firstname = _get_form_value(form, "firstname")
    lastname = _get_form_value(form, "lastname")
    email = _get_form_value(form, "email")
    school = _get_form_value(form, "school")
    minecraft_username = _get_form_value(form, "minecraft_username")

    errors: List[str] = []

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

    return errors


def process_registration(
    *,
    form: Any,
    config: Dict[str, Any],
    serializer: Any,
    request_host_url: str,
) -> Dict[str, Any]:
    """
    Führt den kompletten Registrierungsprozess aus und gibt ein Result-Dict zurück.

    Rückgabe:
      - {"ok": True, "redirect": "success"}
      - {"ok": False, "errors": [...]}

    serializer: URLSafeTimedSerializer (oder kompatibel), muss .dumps() können
    request_host_url: z.B. request.host_url (endet typischerweise mit '/')
    """
    logger.info("Versuche neuen User zu registrieren (Service).")

    # 1) Formfelder lesen
    firstname = _get_form_value(form, "firstname")
    lastname = _get_form_value(form, "lastname")
    email = _get_form_value(form, "email")
    school = _get_form_value(form, "school")
    minecraft_username = _get_form_value(form, "minecraft_username")

    # 2) Pflichtfelder validieren
    errors = validate_registration_form(form)
    if errors:
        return {"ok": False, "errors": errors}

    # 3) E-Mail allowed?
    if not is_email_allowed(email, config):
        accepted_mail_endings = config.get("accepted_mail_endings", []) or []
        logger.info("Abbruch: Unzulässige Mailadresse (nicht in Whitelist und Endung nicht erlaubt).")
        return {
            "ok": False,
            "errors": [
                "Die Registrierung ist nur für E-Mail-Adressen mit folgenden Endungen erlaubt: "
                + ", ".join(accepted_mail_endings)
            ],
        }

    # 4) Accounts pro E-Mail prüfen
    with DatabaseHandler(config) as db:
        count = db.get_user_count_by_email(email)

    max_permitted = get_max_users_per_mail(email, config)
    if count >= max_permitted:
        logger.info(f"Abbruch: Zu viele User mit dieser E-Mail-Adresse registriert ({email})")
        return {
            "ok": False,
            "errors": [f"Es sind bereits {max_permitted} Benutzer mit dieser E-Mail-Adresse registriert."],
        }

    # 5) Username schon registriert?
    with DatabaseHandler(config) as db:
        if db.is_username_exists(minecraft_username):
            logger.info(f"Abbruch: Benutzername bereits in der Datenbank vorhanden ({minecraft_username}).")
            return {"ok": False, "errors": ["Dieser Minecraft-Benutzername ist bereits registriert."]}

    # 6) Offizieller Mojang-Username?
    if not mojang_handler.is_official_username(minecraft_username):
        logger.info(f"Abbruch: Kein gültiger Minecraft-Account ({minecraft_username}).")
        return {"ok": False, "errors": ["Ungültiger Minecraft-Benutzername."]}

    # 7) Token generieren
    logger.info("Generiere Token für Bestätigungslink.")
    token = serializer.dumps(email, salt="email-confirm")

    # 8) Registrierung speichern
    logger.info("Speichere Registrierungsdaten in Datenbank.")
    created_at = datetime.datetime.now()
    with DatabaseHandler(config) as db:
        db.insert_registration(firstname, lastname, email, school, minecraft_username, 0, created_at)

    # 9) Bestätigungslink + Mail senden
    confirmation_link = request_host_url + "confirm_page/" + token
    logger.info("Sende Bestätigungslink per E-Mail.")
    mail_handler.send_confirmation_email(to_email=email, confirmation_link=confirmation_link, firstname=firstname)

    logger.info("Registrierung erfolgreich abgeschlossen.")
    return {"ok": True, "redirect": "success"}

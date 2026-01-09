# app/services/confirmation_service.py

from __future__ import annotations

from typing import Any, Dict, Optional

from itsdangerous import SignatureExpired, BadSignature

from app.infrastructure.log_handler import logger
from app.infrastructure.database_handler import DatabaseHandler
from app.infrastructure import mojang_handler


def _max_age_seconds(config: dict) -> int:
    """
    Gleich wie im alten main.py:
    max_age basiert auf waiting_time_for_db_cleaner * 600
    (also Minuten * 10)
    """
    return int(config["waiting_time_for_db_cleaner"]) * 600


def decode_confirmation_token(*, token: str, serializer: Any, config: dict) -> Dict[str, Any]:
    """
    Decodiert den Bestätigungs-Token und gibt entweder
      {"ok": True, "email": "..."}
    oder
      {"ok": False, "error": "..."}
    zurück.
    """
    try:
        email = serializer.loads(
            token,
            salt="email-confirm",
            max_age=_max_age_seconds(config),
        )
        return {"ok": True, "email": email}

    except SignatureExpired:
        logger.info("Bestätigungslink abgelaufen.")
        return {"ok": False, "error": "Bestätigungslink ist abgelaufen."}

    except BadSignature:
        logger.info("Ungültiger Bestätigungslink.")
        return {"ok": False, "error": "Ungültiger Bestätigungslink."}

    except Exception as e:
        logger.info(f"Fehler beim Decodieren des Tokens: {e}")
        return {"ok": False, "error": "Fehler beim Laden der Bestätigungsseite."}


def confirm_registration_by_token(*, token: str, serializer: Any, config: dict) -> Dict[str, Any]:
    """
    Kompletter Confirm-Flow:
    - Token -> Email
    - Registration confirmed=1 setzen
    - latest minecraft_username holen
    - UUID via Mojang
    - Eintrag in mysql_whitelist

    Rückgabe:
      - {"ok": True, "email": ..., "minecraft_username": ..., "whitelisted": True/False}
      - {"ok": False, "error": "..."}
    """
    decoded = decode_confirmation_token(token=token, serializer=serializer, config=config)
    if not decoded.get("ok"):
        return {"ok": False, "error": decoded.get("error", "Unbekannter Fehler.")}

    email = decoded["email"]

    try:
        logger.info("Versuche Bestätigungsemail zu verarbeiten (Service).")

        # 1) Registrierungsstatus setzen
        logger.info("Aktualisiere Bestätigungsstatus in Datenbank.")
        with DatabaseHandler(config) as db:
            db.confirm_registration(email)

        # 2) Benutzernamen abrufen
        with DatabaseHandler(config) as db:
            minecraft_username = db.get_latest_minecraft_username(email)

        if not minecraft_username:
            logger.info("Kein Benutzername in der DB gefunden.")
            return {
                "ok": False,
                "error": f"Der Minecraft-Benutzername für {email} konnte nicht gefunden werden.",
            }

        # 3) UUID holen + in Whitelist eintragen
        uuid = mojang_handler.get_uuid(minecraft_username)
        if uuid:
            with DatabaseHandler(config) as db:
                db.insert_into_whitelist(uuid, minecraft_username)
            logger.info("Bestätigung erfolgreich abgeschlossen und Spieler in mysql_whitelist eingetragen.")
            return {
                "ok": True,
                "email": email,
                "minecraft_username": minecraft_username,
                "whitelisted": True,
            }
        else:
            logger.error(f"Keine UUID für {minecraft_username} gefunden – Spieler NICHT eingetragen!")
            return {
                "ok": True,
                "email": email,
                "minecraft_username": minecraft_username,
                "whitelisted": False,
            }

    except Exception as e:
        logger.info(f"Fehler beim Bestätigen: {e}")
        return {"ok": False, "error": "Fehler beim Bestätigen der Registrierung."}

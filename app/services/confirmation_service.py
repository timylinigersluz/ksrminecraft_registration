# app/services/confirmation_service.py

from __future__ import annotations

from typing import Any, Dict, Optional

from itsdangerous import SignatureExpired, BadSignature

from app.infrastructure.log_handler import logger
from app.infrastructure.database_handler import DatabaseHandler
from app.infrastructure import mojang_handler


def _token_minutes(config: dict) -> int:
    """
    Neu: waiting_time_for_jobs_and_token (Minuten)
    Fallback: waiting_time_for_db_cleaner (Minuten) oder 60
    """
    return int(config.get("waiting_time_for_jobs_and_token", config.get("waiting_time_for_db_cleaner", 60)))


def _max_age_seconds(config: dict) -> int:
    """
    Token-Gültigkeit in Sekunden.
    """
    return _token_minutes(config) * 60


def _mask_email(email: str) -> str:
    """
    Maskiert E-Mail für Logs:
    max.mustermann@sluz.ch -> m***@sluz.ch
    """
    email = (email or "").strip()
    if "@" not in email:
        return email

    local, domain = email.split("@", 1)
    local = local.strip()
    domain = domain.strip()

    if not local:
        return f"***@{domain}"

    masked_local = (local[0] + "***") if len(local) >= 1 else "***"
    return f"{masked_local}@{domain}"


def _token_tail(token: str, tail_len: int = 10) -> str:
    """
    Gibt nur die letzten Stellen des Tokens zurück (für Logs).
    """
    token = (token or "").strip()
    if not token:
        return ""
    return token if len(token) <= tail_len else token[-tail_len:]


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


def confirm_registration_by_token(
    *,
    token: str,
    serializer: Any,
    config: dict,
    client_ip: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Kompletter Confirm-Flow (korrigiert):
    - Token -> Email
    - Atomar: genau 1 unbestätigten registrations-Eintrag (latest) von confirmed=0 -> 1 umstellen
      -> NUR dann ist Bestätigung erfolgreich
    - minecraft_username aus genau diesem bestätigten Eintrag verwenden
    - UUID via Mojang
    - Eintrag in mysql_whitelist:
        - wenn bereits vorhanden (uuid ODER username), KEIN weiterer Insert
        - stattdessen Log: "User (username) mit der UUID (uuid) ist unterdessen bereits ..."

    Rückgabe:
      - {"ok": True, "email": ..., "minecraft_username": ..., "whitelisted": True/False}
      - {"ok": False, "error": "..."}
    """
    decoded = decode_confirmation_token(token=token, serializer=serializer, config=config)
    if not decoded.get("ok"):
        return {"ok": False, "error": decoded.get("error", "Unbekannter Fehler.")}

    email = str(decoded["email"]).strip()

    # --- LOG START (wie gewünscht) ---
    logger.info("#################### Registrierungsbestätigung erkannt: ####################")
    logger.info(f"E-Mailadresse: {_mask_email(email)}")
    logger.info(f"Client-IP: {client_ip or 'unknown'}")
    logger.info(f"Token: ...{_token_tail(token)}")
    # -------------------------------

    try:
        # 1) Atomar bestätigen: nur wenn ein unbestätigter Eintrag existiert und 0->1 wirklich passiert
        logger.info("Aktualisiere Bestätigungsstatus in Datenbank (atomar).")
        with DatabaseHandler(config) as db:
            confirmed_row = db.confirm_latest_unconfirmed_registration(email)

        if not confirmed_row:
            # Hier landen wir, wenn:
            # - Eintrag gelöscht wurde
            # - kein unbestätigter Eintrag mehr existiert
            # - bereits bestätigt
            logger.info("Keine gültige (unbestätigte) Registrierung für diese E-Mail gefunden.")
            return {"ok": False, "error": "Registrierung nicht gefunden oder bereits bestätigt."}

        minecraft_username = (confirmed_row.get("minecraft_username") or "").strip()
        if not minecraft_username:
            logger.info("Kein Benutzername in der DB gefunden (nach Confirm).")
            return {"ok": False, "error": "Der Minecraft-Benutzername konnte nicht gefunden werden."}

        # 2) UUID holen
        uuid = mojang_handler.get_uuid(minecraft_username)
        if not uuid:
            logger.error(f"Keine UUID für {minecraft_username} gefunden – Spieler NICHT eingetragen!")
            # Bestätigung war DB-seitig erfolgreich, Whitelist aber nicht möglich
            return {
                "ok": True,
                "email": email,
                "minecraft_username": minecraft_username,
                "whitelisted": False,
            }

        # 3) In Whitelist eintragen (ohne Duplikate)
        with DatabaseHandler(config) as db:
            whitelist_result = db.insert_into_whitelist_if_missing(uuid, minecraft_username)

        if whitelist_result == "inserted":
            logger.info(f"Spieler {minecraft_username} mit UUID ({uuid}) erfolgreich in mysql_whitelist eingetragen.")
            logger.info("Bestätigung erfolgreich abgeschlossen und Spieler in mysql_whitelist eingetragen.")
            return {
                "ok": True,
                "email": email,
                "minecraft_username": minecraft_username,
                "whitelisted": True,
            }

        if whitelist_result == "already_exists":
            logger.info(
                "User (%s) mit der UUID (%s) ist unterdessen bereits in mysql_whitelist eingetragen worden.",
                minecraft_username,
                uuid,
            )
            # Nach aussen trotzdem ok, weil registrations korrekt bestätigt wurde
            return {
                "ok": True,
                "email": email,
                "minecraft_username": minecraft_username,
                "whitelisted": True,
            }

        # fallback (sollte selten sein)
        logger.error("Whitelist-Status unbekannt – Spieler evtl. nicht eingetragen.")
        return {
            "ok": True,
            "email": email,
            "minecraft_username": minecraft_username,
            "whitelisted": False,
        }

    except Exception as e:
        logger.error(f"Fehler beim Bestätigen (Service): {e}")
        return {"ok": False, "error": "Fehler beim Bestätigen der Registrierung."}

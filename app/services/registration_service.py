# app/services/registration_service.py

from __future__ import annotations

import datetime
from typing import Any, Dict, List

from app.infrastructure.log_handler import logger
from app.infrastructure.database_handler import DatabaseHandler
from app.infrastructure import mail_handler
from app.infrastructure import mojang_handler

from app.policies.email_policy import is_email_allowed, get_max_users_per_mail


def _get_form_value(form: Any, key: str) -> str:
    # Hilfsfunktion: robustes Auslesen eines Formularfeldes.
    # - form.get(key) kann je nach Framework/Objekt fehlschlagen
    # - Rückgabe ist immer ein getrimmter String (kein None)
    try:
        return (form.get(key) or "").strip()
    except Exception:
        return ""


def _mask_email(email: str) -> str:
    # Maskiert E-Mail-Adressen für Logs, damit keine personenbezogenen Daten
    # im Klartext in Logfiles landen.
    # Beispiel: max.mustermann@sluz.ch -> m***@sluz.ch
    email = (email or "").strip()
    if "@" not in email:
        return email
    local, domain = email.split("@", 1)
    if not local:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


def _waiting_minutes(config: Dict[str, Any]) -> int:
    # Wartedauer (Minuten) für Benutzertexte im Fehlerfall (z. B. Mailversand/Jobs).
    # Falls nicht gesetzt: Default 10 Minuten.
    try:
        return int(config.get("waiting_time_for_jobs_and_token", 10))
    except Exception:
        return 10


def validate_registration_form(form: Any) -> List[str]:
    # Reine Pflichtfeld-Prüfung (ohne Business-Logik).
    # Hier wird nur überprüft, ob die Felder überhaupt ausgefüllt sind.
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
    # Haupt-Flow für eine Registrierung:
    # 1) Eingaben aus Formular lesen
    # 2) Pflichtfelder validieren
    # 3) E-Mail Policy prüfen (bei dir in email_policy.py strikt auf @sluz.ch)
    # 4) Limit Accounts pro E-Mail prüfen
    # 5) Username darf noch nicht registriert sein
    # 6) Mojang Check: Username ist offiziell
    # 7) Token generieren, Registration als unbestätigt speichern (confirmed=0)
    # 8) Bestätigungsmail mit Link senden
    firstname = _get_form_value(form, "firstname")
    lastname = _get_form_value(form, "lastname")
    email = _get_form_value(form, "email")
    school = _get_form_value(form, "school")
    minecraft_username = _get_form_value(form, "minecraft_username")

    # Für Logs (Datenschutz): E-Mail nicht im Klartext loggen
    email_masked = _mask_email(email)

    # --- Logging Start (Audit/Debug) ---
    # Achtung: Der Username wird hier unmaskiert geloggt (kann ok sein,
    # aber wenn du es noch strenger willst, könntest du später auch hier maskieren).
    logger.info("#################### Neue Registrierung aufgegeben: ####################")
    logger.info(f"Name: {lastname}")
    logger.info(f"Vorname: {firstname}")
    logger.info(f"Email: {email_masked}")
    logger.info(f"Schule: {school}")
    logger.info(f"Minecraft-Username: {minecraft_username}")    

    # 1) Pflichtfelder prüfen
    errors = validate_registration_form(form)
    if errors:
        # Abbruch: nichts wird gespeichert, keine Mail, kein Token
        logger.info("Abbruch: Pflichtfelder fehlen oder sind leer.")
        logger.info("  Fehler: " + " | ".join(errors))
        return {"ok": False, "errors": errors}

    # 2) E-Mail Policy prüfen
    # WICHTIG: Du hast is_email_allowed() bereits so angepasst, dass NUR @sluz.ch erlaubt ist.
    # Falls die Policy False liefert -> Abbruch mit Hinweistext.
    if not is_email_allowed(email, config):
        accepted_mail_endings = config.get("accepted_mail_endings", []) or []
        logger.info(f"Abbruch: E-Mailadresse ungültig ({email_masked}).")
        return {
            "ok": False,
            "errors": [
                "Die Registrierung ist nur für E-Mail-Adressen mit folgenden Endungen erlaubt: "
                + ", ".join(accepted_mail_endings)
            ],
        }

    logger.info(f"Email ({email_masked}) ist zulässig.")

    # 3) DB: Anzahl Accounts pro E-Mail prüfen
    # -> schützt gegen zu viele Accounts unter der gleichen Mailadresse
    try:
        with DatabaseHandler(config) as db:
            count = db.get_user_count_by_email(email)
    except Exception as e:
        # DB-Probleme: Benutzer bekommt generischen Fehler, Log enthält Details
        logger.error(f"Abbruch: Konnte Anzahl Accounts pro Mail nicht prüfen ({email_masked}): {e}")
        return {"ok": False, "errors": ["Interner Fehler (Datenbank). Bitte später erneut versuchen."]}

    # Maximal erlaubte Accounts pro Mail wird über Policy/Config bestimmt
    max_permitted = get_max_users_per_mail(email, config)
    logger.info(f"Email-Adresse hat bereits {count} Accounts auf dem Server (Limit: {max_permitted}).")

    # Überschreitet Limit -> Abbruch
    if count >= max_permitted:
        logger.info(f"Abbruch: Zu viele User mit dieser E-Mail-Adresse registriert ({email_masked}).")
        return {"ok": False, "errors": [f"Es sind bereits {max_permitted} Benutzer mit dieser E-Mail-Adresse registriert."]}

    # 4) DB: Username darf nicht schon existieren
    # -> verhindert Doppelregistrierungen auf Username-Ebene
    try:
        with DatabaseHandler(config) as db:
            exists = db.is_username_exists(minecraft_username)
    except Exception as e:
        logger.error(f"Abbruch: Konnte Username-Existenz nicht prüfen ({minecraft_username}): {e}")
        return {"ok": False, "errors": ["Interner Fehler (Datenbank). Bitte später erneut versuchen."]}

    if exists:
        logger.info(f"Abbruch: Username ({minecraft_username}) ist bereits registriert.")
        return {"ok": False, "errors": ["Dieser Minecraft-Benutzername ist bereits registriert."]}

    logger.info(f"Username ({minecraft_username}) ist noch nicht registriert.")

    # 5) Mojang Check: Username muss ein offizieller Minecraft-Account sein
    # -> schützt vor Tippfehlern / Fake-Accounts
    try:
        is_official = mojang_handler.is_official_username(minecraft_username)
    except Exception as e:
        # Mojang/Minecraft API down o. ä.: lieber sauber abbrechen
        logger.error(f"Abbruch: Mojang-Check fehlgeschlagen ({minecraft_username}): {e}")
        return {"ok": False, "errors": ["Minecraft-Account konnte nicht geprüft werden. Bitte später erneut versuchen."]}

    if not is_official:
        logger.info(f"Abbruch: Username ({minecraft_username}) ist kein offizieller Minecraft-Account.")
        return {"ok": False, "errors": ["Ungültiger Minecraft-Benutzername."]}

    logger.info(f"Username ({minecraft_username}) ist ein offizieller Minecraft-Account.")
    logger.info("Alle Bedingungen sind erfüllt. Registrierung ist zulässig.")
    logger.info("Generiere Token für Bestätigungslink.")

    # 6) Token für Bestätigungslink erstellen
    # Payload ist hier die E-Mail (Serializer + salt="email-confirm")
    try:
        token = serializer.dumps(email, salt="email-confirm")
    except Exception as e:
        logger.error(f"Abbruch: Token konnte nicht generiert werden ({email_masked}): {e}")
        return {"ok": False, "errors": ["Interner Fehler (Token). Bitte später erneut versuchen."]}

    # 7) Registration speichern (confirmed=0, unbestätigt)
    logger.info("Speichere Registrierungsdaten in Datenbank.")
    created_at = datetime.datetime.now()
    try:
        with DatabaseHandler(config) as db:
            db.insert_registration(firstname, lastname, email, school, minecraft_username, 0, created_at)
    except Exception as e:
        logger.error(f"Abbruch: Registrierung konnte nicht gespeichert werden ({email_masked}, {minecraft_username}): {e}")
        return {"ok": False, "errors": ["Interner Fehler (Speichern). Bitte später erneut versuchen."]}

    # 8) Link zusammensetzen und Bestätigungsmail senden
    # Hinweis: request_host_url muss korrekt sein (typischerweise endet es mit '/')
    confirmation_link = request_host_url + "confirm_page/" + token
    logger.info(f"Sende Bestätigungslink per E-Mail an ({email_masked}).")

    try:
        # Versand der Bestätigungsmail an den Benutzer
        mail_handler.send_confirmation_email(to_email=email, confirmation_link=confirmation_link, firstname=firstname)
    except Exception as e:
        # Mailversand fehlgeschlagen:
        # - Registrierung bleibt gespeichert (confirmed=0)
        # - Admin/Team wird informiert
        logger.error(f"Mailversand fehlgeschlagen ({email_masked}): {e}")

        try:
            # Admin-Alert: enthält Details, damit das Team nachfassen kann
            mail_handler.send_admin_alert_email(
                admin_email="info@ksrminecraft.ch",
                user_email=email,
                firstname=firstname,
                lastname=lastname,
                school=school,
                minecraft_username=minecraft_username,
                token=token,
                confirmation_link=confirmation_link,
                error_message=str(e),
            )
            logger.info("Admin-Alert wurde gesendet.")
        except Exception as alert_err:
            # Wenn selbst der Admin-Alert nicht geht, bleibt nur Logging
            logger.error(f"Admin-Alert konnte NICHT gesendet werden: {alert_err}")

        # Benutzerfreundliche Meldung mit Wartezeit-Hinweis
        wait_min = _waiting_minutes(config)
        return {
            "ok": False,
            "errors": [
                "Die Registrierung wurde gespeichert, aber die E-Mail konnte nicht gesendet werden. "
                "Das Team wurde informiert und meldet sich bei dir. "
                f"Wenn du innerhalb von {wait_min} Minuten nichts hörst, melde dich auf unserem Discord "
                "oder versuche es danach erneut."
            ],
        }

    # Abschluss: Registrierung ist gespeichert, Mail ist raus, jetzt muss der User nur noch bestätigen
    logger.info("Erster Teil Registrierung erfolgreich abgeschlossen – warte auf Bestätigung für die definitive Registrierung.")
    return {"ok": True, "redirect": "success"}

# app/jobs/cleanup_unconfirmed.py

from __future__ import annotations

from app.infrastructure.log_handler import logger
from app.infrastructure.database_handler import DatabaseHandler


def _jobs_interval_minutes(config: dict) -> int:
    """
    Zentrales Job-Intervall (Minuten).
    Neu: waiting_time_for_jobs
    Fallback (alt): waiting_time_for_db_cleaner
    """
    return int(config.get("waiting_time_for_jobs", config.get("waiting_time_for_db_cleaner", 10)))


def cleanup_unconfirmed_once(config: dict) -> int:
    """
    Einmaliger Durchlauf:
    - sucht unbestätigte Registrierungen, die älter als waiting_time_for_jobs (Minuten) sind
    - löscht diese Einträge
    - loggt Details (Email + Minecraft-Username)
    Rückgabe: Anzahl gelöschter Einträge
    """
    time_difference = _jobs_interval_minutes(config)

    with DatabaseHandler(config) as db:
        unconfirmed = db.get_unconfirmed_registrations_before(time_difference)
        deleted_count = db.delete_unconfirmed_registrations_before(time_difference)

    if deleted_count > 0:
        logger.info(f"{deleted_count} unbestätigte Einträge wurden gelöscht:")
        for reg in unconfirmed:
            try:
                email = reg[3]
                minecraft_username = reg[5]
                logger.info(f"Email: {email}, Minecraft-Benutzername: {minecraft_username}")
            except Exception:
                logger.info(f"Gelöschter Eintrag: {reg}")
    else:
        logger.info("Es wurden keine unbestätigten Einträge gelöscht.")

    return int(deleted_count)

# app/jobs/cleanup_removed.py

from app.infrastructure.database_handler import DatabaseHandler
from app.infrastructure.log_handler import logger


def _normalize_username(value: str) -> str:
    return (value or "").strip().lower()


def cleanup_removed_registrations_once(config: dict) -> int:
    """
    Ein einmaliger Durchlauf:
    - liest bestätigte Registrations
    - liest mysql_whitelist
    - entfernt Registrations, deren username nicht mehr in mysql_whitelist ist
    Gibt Anzahl gelöschter Einträge zurück.
    """
    deleted = 0

    with DatabaseHandler(config) as db:
        whitelist_users = {_normalize_username(u) for u in db.get_whitelist_usernames()}
        regs = db.get_confirmed_registrations_basic()

        if not regs:
            logger.info("cleanup_removed: Keine bestätigten Registrations gefunden.")
            return 0

        to_delete = []
        for reg_id, email, mc_user in regs:
            if not mc_user:
                continue
            if _normalize_username(mc_user) not in whitelist_users:
                to_delete.append((reg_id, email, mc_user))

        if not to_delete:
            logger.info("cleanup_removed: Keine entfernten Whitelist-User gefunden – nichts zu löschen.")
            return 0

        logger.info(f"cleanup_removed: {len(to_delete)} Registrations ohne Whitelist-Eintrag gefunden → werden gelöscht.")
        for reg_id, email, mc_user in to_delete:
            try:
                rows = db.delete_registration_by_id(int(reg_id))
                if rows:
                    deleted += rows
                    logger.info(f"cleanup_removed: gelöscht id={reg_id}, email={email}, user={mc_user}")
            except Exception as e:
                logger.error(f"cleanup_removed: Fehler beim Löschen id={reg_id} user={mc_user}: {e}")

    return deleted

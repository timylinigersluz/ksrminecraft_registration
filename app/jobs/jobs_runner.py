# app/jobs/jobs_runner.py

from __future__ import annotations

import time
import threading

from app.infrastructure.log_handler import logger
from app.jobs.cleanup_unconfirmed import cleanup_unconfirmed_once
from app.jobs.cleanup_removed import cleanup_removed_registrations_once


def _jobs_interval_minutes(config: dict) -> int:
    """
    Zentrales Job-Intervall (Minuten).
    Neu: waiting_time_for_jobs_and_token
    Fallback: waiting_time_for_db_cleaner / waiting_time_for_removed_cleanup / 10
    """
    return int(
        config.get(
            "waiting_time_for_jobs_and_token",
            config.get("waiting_time_for_db_cleaner", config.get("waiting_time_for_removed_cleanup", 10)),
        )
    )


def jobs_loop(config: dict):
    """
    Endlosschleife:
      1) cleanup_unconfirmed_once
      2) cleanup_removed_registrations_once
      3) sleep(waiting_time_for_jobs_and_token)
    """
    while True:
        try:
            logger.info("jobs_runner: Starte Durchlauf (unconfirmed -> removed).")

            deleted_unconfirmed = cleanup_unconfirmed_once(config)
            logger.info(f"jobs_runner: unconfirmed gelöscht: {deleted_unconfirmed}")

            deleted_removed = cleanup_removed_registrations_once(config)
            logger.info(f"jobs_runner: removed gelöscht: {deleted_removed}")

            logger.info("jobs_runner: Durchlauf abgeschlossen.")

        except Exception as e:
            logger.error(f"jobs_runner: Fehler im Durchlauf: {e}")

        time.sleep(_jobs_interval_minutes(config) * 60)


def start_jobs_thread(config: dict) -> threading.Thread:
    """
    Startet den kombinierten Job-Runner als daemon Thread.
    """
    t = threading.Thread(target=jobs_loop, args=(config,), daemon=True)
    t.start()
    logger.info("jobs_runner: Thread gestartet.")
    return t

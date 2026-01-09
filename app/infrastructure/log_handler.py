# app/infrastructure/log_handler.p
import logging
import os
from datetime import datetime

# Konfigurieren des Loggers
logger = logging.getLogger("my_logger")
logger.setLevel(logging.INFO)

# WICHTIG:
# - Mehrfach-Imports dürfen keine Handler doppelt hinzufügen
# - propagate = False verhindert doppelte Ausgaben über Root-Logger
logger.propagate = False


def _configure_logger_once() -> None:
    """
    Richtet Handler nur einmal ein (idempotent).
    """
    if getattr(logger, "_ksr_configured", False):
        return

    # Definiere Log-Verzeichnis (wird in Docker als Volume gemountet: /app/logs)
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Tageslogfile
    log_filename = datetime.now().strftime("%Y-%m-%d") + "_logfile.log"
    file_handler = logging.FileHandler(os.path.join(log_dir, log_filename), encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(fmt)

    # Konsole
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(fmt)

    # Fehlerlog
    exception_handler = logging.FileHandler(os.path.join(log_dir, "fehler.log"), encoding="utf-8")
    exception_handler.setLevel(logging.ERROR)
    exception_handler.setFormatter(fmt)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.addHandler(exception_handler)

    # Marker setzen, damit wir nicht doppelt konfigurieren
    logger._ksr_configured = True


# Sofort beim Import konfigurieren (aber nur einmal)
_configure_logger_once()

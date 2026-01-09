# run.py (lokaler DEV-Start)
import signal
import sys

from app import create_app
from app.infrastructure.log_handler import logger


def _cleanup_handler(signum, frame):
    logger.info("Server wird beendet.")
    sys.exit(0)


if __name__ == "__main__":
    app = create_app()

    # Sauber beenden (z.B. Ctrl+C / SIGTERM)
    signal.signal(signal.SIGTERM, _cleanup_handler)

    cfg = app.config["APP_CONFIG"]
    debug = bool(cfg.get("debug", False))

    # Lokal: 127.0.0.1, in Docker/Gunicorn wird sowieso main:application genutzt
    app.run(host="127.0.0.1", port=5000, debug=debug)

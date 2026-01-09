# tests/preview_browser_test.py
from __future__ import annotations

import sys
import threading
import time
import webbrowser
from pathlib import Path

from werkzeug.serving import make_server


# ------------------------------------------------------------
# Projekt-Root in sys.path aufnehmen, damit "import app" klappt
# ------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app  # noqa: E402


def build_sample_config() -> dict:
    return {
        "debug": True,

        # Branding / UI
        "sender_display_name": "KSR Minecraft Team",
        "sender_organization": "Kantonsschule Reussbühl",

        # Policies
        "accepted_mail_endings": ["@sluz.ch"],
        "max_users_per_mail": 3,
        "email_user_limits": {
            "team@ksrminecraft.ch": 10,
            "timothee.liniger@sluz.ch": 10,
        },

        # Token TTL / Cleaner
        "waiting_time_for_db_cleaner": 10,

        # Mail (nur fürs Preview)
        "smtp_server": "ksrminecraft.ch",
        "smtp_port": 465,
        "smtp_username": "team@ksrminecraft.ch",
        "imap_port": 993,
        "sent_folder": "Sent",
        "imap_save_sent": True,
    }


def start_server(app, host: str, port: int):
    server = make_server(host, port, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def main():
    host = "127.0.0.1"
    port = 5000
    base = f"http://{host}:{port}"

    app = create_app()
    app.config["APP_CONFIG"] = build_sample_config()

    server, _thread = start_server(app, host, port)
    time.sleep(0.25)

    url = f"{base}/preview"
    print(f"Öffne Preview-Übersicht: {url}")
    webbrowser.open(url, new=1)

    print("Server läuft. Beenden mit CTRL+C.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStoppe Server...")
        server.shutdown()
        print("OK.")


if __name__ == "__main__":
    main()

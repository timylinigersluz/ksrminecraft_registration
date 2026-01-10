# app/__init__.py

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from flask import Flask, request
from itsdangerous import URLSafeTimedSerializer

from app.infrastructure.log_handler import logger

# Blueprints
from app.routes.registration_routes import registration_bp
from app.routes.confirmation_routes import confirmation_bp
from app.routes.preview_routes import preview_bp

# Jobs
from app.jobs.jobs_runner import start_jobs_thread


ROOT_DIR = Path(__file__).resolve().parent.parent  # Projektroot (da wo config.json liegt)


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_app_config(config_path: str | Path = "config.json") -> Dict[str, Any]:
    path = Path(config_path)
    if not path.is_absolute():
        path = ROOT_DIR / path
    return _load_json(path)


def load_secret_key(secret_path: str | Path = "secret_key.json") -> str:
    path = Path(secret_path)
    if not path.is_absolute():
        path = ROOT_DIR / path
    data = _load_json(path)
    secret = data.get("secret_key")
    if not secret:
        raise RuntimeError("secret_key fehlt in secret_key.json")
    return secret


def create_app() -> Flask:
    """
    App Factory:
    - lädt config + secret_key
    - erstellt Flask App (Templates/Static aus app/)
    - erstellt serializer
    - registriert blueprints
    - initialisiert DB + startet Jobs
    """
    cfg = load_app_config("config.json")
    secret = load_secret_key("secret_key.json")

    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    # zentral verfügbar machen
    app.config["APP_CONFIG"] = cfg
    app.config["SECRET_KEY"] = secret
    app.config["SERIALIZER"] = URLSafeTimedSerializer(secret)

    logger.info("App initialisiert: Config + Secret + Serializer geladen.")

    # ----------------------------
    # CORS für Embedded-Formular
    # ----------------------------
    @app.after_request
    def add_cors_headers(resp):
        origin = request.headers.get("Origin")

        allowed = {
            "https://ksrminecraft.ch",
            "https://www.ksrminecraft.ch",
            # optional lokal fürs Testen:
            "http://127.0.0.1:5000",
            "http://localhost:5000",
        }

        if origin in allowed:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Vary"] = "Origin"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Accept, X-Requested-With"
            resp.headers["Access-Control-Max-Age"] = "86400"

        return resp

    # Blueprints registrieren (Routes)
    app.register_blueprint(registration_bp)
    app.register_blueprint(confirmation_bp)
    app.register_blueprint(preview_bp)

    logger.info("Blueprints registriert.")

    # DB initialisieren + Jobs starten
    _init_database_and_jobs(app)

    return app


def _init_database_and_jobs(app: Flask) -> None:
    """
    DB init + Background Jobs.
    """
    from app.infrastructure.database_handler import DatabaseHandler  # late import (verhindert Import-Zyklen)

    cfg = app.config["APP_CONFIG"]

    logger.info("Initialisiere DB (create_table).")
    with DatabaseHandler(cfg) as db:
        db.create_table()

    # Kombinierter Runner (unconfirmed -> removed)
    try:
        start_jobs_thread(cfg)
    except Exception as e:
        logger.error(f"Konnte jobs_runner Thread nicht starten: {e}")

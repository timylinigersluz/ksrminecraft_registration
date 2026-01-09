# app/infrastructure/mojang_handler.py

from __future__ import annotations

from typing import Optional
import requests

from app.infrastructure.log_handler import logger

# Simple in-process cache (optional, hilft gegen Rate-Limits)
_UUID_CACHE: dict[str, Optional[str]] = {}


def _timeout_seconds(config: dict | None = None) -> float:
    """
    Timeout in Sekunden.
    Optional via config.json:
      "mojang_timeout_seconds": 5
    """
    if config and "mojang_timeout_seconds" in config:
        try:
            return float(config["mojang_timeout_seconds"])
        except Exception:
            pass
    return 5.0


def is_official_username(username: str, config: dict | None = None) -> bool:
    """
    Prüft, ob der Minecraft-Username existiert (Mojang-API).
    Gibt True zurück, wenn Nutzer existiert, sonst False.
    """
    username = (username or "").strip()
    if not username:
        return False

    api_url = f"https://api.mojang.com/users/profiles/minecraft/{username}"
    timeout = _timeout_seconds(config)

    try:
        resp = requests.get(api_url, timeout=timeout)

        if resp.status_code == 200:
            return True

        # 204/404 -> kein User (je nach Verhalten/Änderungen), wir behandeln alles !=200 als "nicht vorhanden"
        if resp.status_code in (204, 404):
            return False

        logger.warning(f"Mojang Username-Check: unerwarteter Status {resp.status_code} für '{username}'")
        return False

    except requests.RequestException as e:
        logger.error(f"Mojang Username-Check: Request-Fehler für '{username}': {e}")
        return False


def get_uuid(username: str, config: dict | None = None) -> Optional[str]:
    """
    Liefert die UUID (ohne Bindestriche) zu einem Minecraft-Username via Mojang-API.
    Gibt None zurück, wenn nicht gefunden oder Fehler.
    """
    username = (username or "").strip()
    if not username:
        return None

    # Cache
    key = username.lower()
    if key in _UUID_CACHE:
        return _UUID_CACHE[key]

    api_url = f"https://api.mojang.com/users/profiles/minecraft/{username}"
    timeout = _timeout_seconds(config)

    try:
        resp = requests.get(api_url, timeout=timeout)

        if resp.status_code != 200:
            if resp.status_code in (204, 404):
                _UUID_CACHE[key] = None
                return None

            logger.warning(f"Mojang UUID-Request: unerwarteter Status {resp.status_code} für '{username}'")
            _UUID_CACHE[key] = None
            return None

        data = resp.json()
        uuid = data.get("id")
        if not uuid:
            _UUID_CACHE[key] = None
            return None

        _UUID_CACHE[key] = uuid
        return uuid

    except requests.RequestException as e:
        logger.error(f"Mojang UUID-Request: Request-Fehler für '{username}': {e}")
        _UUID_CACHE[key] = None
        return None

    except ValueError as e:
        # JSON parse error
        logger.error(f"Mojang UUID-Request: JSON-Fehler für '{username}': {e}")
        _UUID_CACHE[key] = None
        return None

from mctools import RCONClient
import json
import requests
import socket
from log_handler import *

# RCON-Zugangsdaten laden
logger.info("Lade RCON-Zugangsdaten aus JSON-Datei.")
with open('config.json') as file:
    config = json.load(file)

# Zugangsdaten
host = config['rcon_host']
port = config['rcon_port']
password = config['rcon_password']


# RCON-Verbindung herstellen
def connect_rcon() -> RCONClient | None:
    if config.get("debug", False):
        logger.info("DEBUG: RCON deaktiviert, keine Verbindung hergestellt.")
        return None
    try:
        logger.info("Stelle RCON-Verbindung her.")
        # Timeout setzen, damit Worker nicht hängen bleibt
        socket.setdefaulttimeout(5)
        rcon = RCONClient(host, port=port)
        rcon.login(password)
        return rcon
    except Exception as e:
        logger.error(f"RCON-Verbindung fehlgeschlagen: {e}")
        return None


# Whitelist-Status prüfen
def is_whitelistened(username: str) -> bool:
    logger.info(f"Prüfe, ob Spieler {username} bereits auf der Whitelist ist.")
    rcon = connect_rcon()
    if not rcon:
        return False
    try:
        response = rcon.command("whitelist list")
        if response and username in response:
            logger.info(f"Spieler {username} ist bereits auf der Whitelist.")
            return True
        logger.info(f"Spieler {username} ist noch nicht auf der Whitelist.")
        return False
    except Exception as e:
        logger.error(f"Fehler beim Abfragen der Whitelist: {e}")
        return False


# Spieler zur Whitelist hinzufügen
def whitelist_add(username: str) -> bool:
    logger.info(f"Versuche Spieler {username} in die Whitelist einzutragen.")
    if not is_official_username(username):
        logger.info(f"User {username} ist kein offizieller Minecraft-Account.")
        return False

    if is_whitelistened(username):
        logger.info(f"User {username} ist bereits whitelisted.")
        return False

    rcon = connect_rcon()
    if not rcon:
        return False
    try:
        response = rcon.command(f"whitelist add {username}")
        logger.info(f"RCON Antwort: {response}")
        return True
    except Exception as e:
        logger.error(f"Fehler beim Hinzufügen zur Whitelist: {e}")
        return False


# Abfrage, ob Benutzername offiziell von Mojang ist
def is_official_username(username: str) -> bool:
    logger.info(f"Prüfe, ob Benutzername {username} ein offizieller Mojang-Account ist.")
    api_url = f'https://api.mojang.com/users/profiles/minecraft/{username}'
    try:
        response = requests.get(api_url, timeout=5)
        if response.status_code == 200:
            logger.info(f"Benutzername {username} ist offiziell.")
            return True
        elif response.status_code in (204, 404):
            logger.info(f"Benutzername {username} ist nicht offiziell.")
            return False
        else:
            logger.warning(f"Unerwarteter Statuscode {response.status_code} bei Mojang-Abfrage.")
            return False
    except Exception as e:
        logger.error(f"Fehler bei Mojang-API-Abfrage: {e}")
        return False


# Alle Whitelisted-Spieler ausgeben
def whitelisted_players() -> list:
    logger.info("Gebe alle Spieler auf der Whitelist aus.")
    rcon = connect_rcon()
    if not rcon:
        return []
    try:
        response = rcon.command("whitelist list")
        return response.split("\n") if response else []
    except Exception as e:
        logger.error(f"Fehler beim Abfragen der Whitelist-Liste: {e}")
        return []

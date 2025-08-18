import requests
from log_handler import logger

def is_official_username(username: str) -> bool:
    logger.info(f"Prüfe, ob Benutzername {username} ein offizieller Mojang-Account ist.")
    api_url = f'https://api.mojang.com/users/profiles/minecraft/{username}'
    response = requests.get(api_url)

    if response.status_code == 200:
        logger.info(f"Benutzername {username} ist offiziell.")
        return True
    elif response.status_code in (204, 404):
        logger.info(f"Benutzername {username} ist nicht offiziell.")
        return False
    else:
        logger.error(f"Fehler bei Mojang-API für {username}: {response.status_code}")
        return False
    

def get_uuid(username: str) -> str | None:
    """
    Holt die UUID zu einem Minecraft-Username über die Mojang API.
    """
    url = f"https://api.mojang.com/users/profiles/minecraft/{username}"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        uuid = data.get("id")
        logger.info(f"UUID für {username} gefunden: {uuid}")
        return uuid
    else:
        logger.info(f"Keine UUID für {username} gefunden.")
        return None
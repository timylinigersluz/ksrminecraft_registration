# test_rcon.py
import RCON_handler

def main():
    print("---- RCON TEST START ----")

    # Test: offizieller Username?
    username = "Notch"   # Beispielname, kann geändert werden
    print(f"Prüfe, ob {username} ein offizieller Username ist...")
    print("Ergebnis:", RCON_handler.is_official_username(username))

    # Test: Whitelist prüfen
    print(f"Prüfe, ob {username} auf der Whitelist steht...")
    print("Ergebnis:", RCON_handler.is_whitelistened(username))

    # Test: Spieler hinzufügen (falls nicht schon whitelisted)
    print(f"Versuche {username} zur Whitelist hinzuzufügen...")
    success = RCON_handler.whitelist_add(username)
    print("Ergebnis:", success)

    # Test: alle Spieler ausgeben
    print("Aktuelle Whitelist:")
    players = RCON_handler.whitelisted_players()
    print(players)

    print("---- RCON TEST ENDE ----")


if __name__ == "__main__":
    main()

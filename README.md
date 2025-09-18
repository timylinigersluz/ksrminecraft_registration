# KSRMinecraft Registration API

Die **KSRMinecraft Registration API** ist ein Programm, das im Rahmen
des Freifachs *Minecraft und Informatik* an der Kantonsschule Reussbühl
(KSR) entwickelt wurde.\
Es ermöglicht eine sichere Registrierung für den KSR-Minecraft-Server,
indem alle Spieler ihre offizielle Sluz-Mailadresse verifizieren müssen,
bevor sie auf die Whitelist des Servers gelangen.

------------------------------------------------------------------------

## Features

-   Registrierung von Minecraft-Spielern über ein Webformular
-   Validierung der Sluz-E-Mail-Adresse und des Minecraft-Benutzernamens
-   Versand eines Bestätigungslinks per E-Mail
-   Automatische Eintragung in die Whitelist nach erfolgreicher
    Verifizierung
-   Speicherung der Registrierungsdaten in einer MySQL-Datenbank
-   Automatisches Bereinigen nicht bestätigter Registrierungen
-   Verwaltung und Logging aller Vorgänge
-   Unterstützung für RCON zur direkten Whitelist-Interaktion mit dem
    Minecraft-Server
-   Docker-Deployment möglich

------------------------------------------------------------------------

## Beispiel Use Case

1.  Ein Spieler gibt auf der KSRMinecraft-Website **Name, Vorname,
    E-Mail, Schule und Minecraft-Username** an.\
2.  Die Daten werden an diese API übermittelt.\
3.  Das Programm prüft die Eingaben (Sluz-E-Mail, gültiger Username,
    maximale Anzahl Accounts pro Mail etc.).\
4.  Ein einmaliger Bestätigungsschlüssel wird generiert und an die
    E-Mail des Spielers gesendet.\
5.  Der Spieler klickt auf den Link in der E-Mail.\
6.  Wenn der Schlüssel korrekt ist, wird der Spieler automatisch in die
    **Whitelist** des Minecraft-Servers eingetragen.\
7.  Eine **Bestätigungsseite** zeigt den Erfolg der Registrierung an.

------------------------------------------------------------------------

## Server Infrastruktur

Die API ist nur ein Teil der gesamten Anmelde-Infrastruktur:

-   **KSRMinecraft-Website**: Formular zur Eingabe der Daten
-   **Registrierungs-API (dieses Projekt)**: Verarbeitung, Validierung,
    Mailversand, Datenbankeinträge
-   **Mail-Server**: Versand der Bestätigungslinks (z. B. Gmail oder
    eigener Mailserver `@ksrminecraft.ch`)
-   **MySQL-Datenbank**: Speicherung der Registrierungsdaten und
    Whitelist-Einträge
-   **Minecraft-Server (Paper + Plugin `mysql_whitelist`)**: nutzt
    dieselbe Datenbank, um die Whitelist zu verwalten

------------------------------------------------------------------------

## API Endpoints

### `/register`

-   **GET**: zeigt das Registrierungsformular an\
-   **POST**: verarbeitet die Registrierungsdaten
    -   Parameter:
        -   `firstname` (string)\
        -   `lastname` (string)\
        -   `email` (string)\
        -   `school` (string)\
        -   `minecraft_username` (string)

### `/confirm/<token>`

-   **GET**: verarbeitet den Bestätigungslink\
-   Parameter: `token`\
-   Rückgabe: Erfolgs- oder Fehlermeldung (HTML-Page)

### `/success`

-   Erfolgsseite nach abgeschlossener Registrierung

### `/error`

-   Fehlerseite mit Rückmeldung zu falschen Eingaben

------------------------------------------------------------------------

## Datenbank

Es werden zwei Tabellen benötigt:

### `registrations`

Speichert alle Anmeldedaten.

  Spalte               Typ            Beschreibung
  -------------------- -------------- --------------------------------
  id                   INT (PK)       Eindeutige ID
  firstname            VARCHAR(255)   Vorname
  lastname             VARCHAR(255)   Nachname
  email                VARCHAR(255)   E-Mail
  school               VARCHAR(255)   Schule
  minecraft_username   VARCHAR(255)   Minecraft-Username
  confirmed            TINYINT(1)     0 = unbestätigt, 1 = bestätigt
  created_at           TIMESTAMP      Erstellungszeit
  timestamp            TIMESTAMP      Letzte Änderung

### `mysql_whitelist`

Wird vom Minecraft-Plugin `mysql_whitelist` genutzt.

  Spalte   Typ            Beschreibung
  -------- -------------- --------------------
  UUID     VARCHAR(100)   Minecraft-UUID
  user     VARCHAR(100)   Minecraft-Username

------------------------------------------------------------------------

## Konfiguration

Die Konfiguration erfolgt über **`config.json`**:

-   **General**: Debug-Modus, max. Benutzer pro E-Mail, erlaubte
    Domains\
-   **Web**: Support-Mail, Discord-Link, Verbindungs-URL\
-   **Database**: Zugangsdaten MySQL\
-   **Email**: SMTP-Einstellungen für Mailversand\
-   **RCON**: Host, Port und Passwort für Minecraft-Server

Beispielauszug:

``` json
{
  "debug": false,
  "max_users_per_mail": 3,
  "accepted_mail_endings": ["sluz.ch"],
  "db_host": "ksrminecraft.ch",
  "db_user": "regadmin",
  "db_password": "******",
  "db_database": "KSRMC-Registration",
  "smtp_server": "smtp.gmail.com",
  "smtp_port": 587,
  "smtp_username": "ksrminecraftwhitelister@gmail.com",
  "smtp_password": "******",
  "rcon_host": "45.154.49.72",
  "rcon_port": 25575,
  "rcon_password": "******"
}
```

Der geheime Key zur Token-Erstellung wird in **`secret_key.json`**
gespeichert:

``` json
{
  "secret_key": "zufälliger_sicherer_string"
}
```

------------------------------------------------------------------------

## Deployment

### Mit Docker

``` bash
docker build -t ksrminecraft-registration .
docker-compose up -d
```

### Ohne Docker

``` bash
python main.py
```

------------------------------------------------------------------------

## Projektstruktur

    .
    ├── main.py                 # Flask Webserver & Routing
    ├── database_handler.py     # Datenbankzugriff
    ├── RCON_handler.py         # Minecraft-Whitelist Verwaltung via RCON
    ├── mail_handler.py         # E-Mail Versand
    ├── log_handler.py          # Logging
    ├── config.json             # Konfiguration
    ├── secret_key.json         # Secret Key für Tokens
    ├── templates/              # HTML-Templates (Flask Jinja2)
    │   ├── index.html
    │   ├── registration.html
    │   ├── success.html
    │   ├── error.html
    └── requirements.txt        # Python-Abhängigkeiten

------------------------------------------------------------------------

## Installation

1.  Repository klonen

    ``` bash
    git clone https://github.com/ksrminecraft/registration-api.git
    cd registration-api
    ```

2.  Virtuelle Umgebung erstellen und Pakete installieren

    ``` bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **config.json** und **secret_key.json** anpassen\

4.  Server starten

    ``` bash
    python main.py
    ```

------------------------------------------------------------------------

## Lizenz

Dieses Projekt wurde für das Freifach Minecraft & Informatik der
Kantonsschule Reussbühl entwickelt.\
Nutzung nur innerhalb der Schulinfrastruktur vorgesehen.

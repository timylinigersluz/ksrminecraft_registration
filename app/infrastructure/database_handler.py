# app/infrastructure/database_handler.py

import mysql.connector
from datetime import datetime, timedelta

from .log_handler import logger


class DatabaseHandler:
    def __init__(self, config: dict):
        self.config = config
        self.conn = None
        self.cursor = None

    def __enter__(self):
        try:
            self.conn = mysql.connector.connect(
                host=self.config["db_host"],
                port=self.config["db_port"],
                user=self.config["db_user"],
                password=self.config["db_password"],
                database=self.config["db_database"],
            )
            self.cursor = self.conn.cursor()
        except mysql.connector.Error as error:
            logger.error(f"Fehler bei der Verbindung zur Datenbank: {error}")
            raise
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        try:
            if self.cursor:
                self.cursor.close()
        finally:
            if self.conn:
                self.conn.close()

    def create_table(self):
        try:
            logger.info("Erstelle Tabelle, falls sie noch nicht existiert.")
            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS registrations (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    firstname VARCHAR(255),
                    lastname VARCHAR(255),
                    email VARCHAR(255),
                    school VARCHAR(255),
                    minecraft_username VARCHAR(255),
                    confirmed TINYINT(1) DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self.conn.commit()
        except mysql.connector.Error as error:
            logger.error(f"Fehler beim Erstellen der Tabelle: {error}")
            raise

    # -------------------------
    # Unconfirmed cleanup (bestehend)
    # -------------------------
    def get_unconfirmed_registrations_before(self, time_difference_minutes: int):
        query = """
            SELECT * FROM registrations
            WHERE confirmed = 0 AND created_at < %s
        """
        timestamp = datetime.now() - timedelta(minutes=time_difference_minutes)
        with self.conn.cursor() as cursor:
            cursor.execute(query, (timestamp,))
            return cursor.fetchall()

    def delete_unconfirmed_registrations_before(self, time_difference_minutes: int) -> int:
        query = """
            DELETE FROM registrations
            WHERE confirmed = 0 AND created_at < %s
        """
        timestamp = datetime.now() - timedelta(minutes=time_difference_minutes)
        with self.conn.cursor() as cursor:
            cursor.execute(query, (timestamp,))
            self.conn.commit()
            return cursor.rowcount

    # -------------------------
    # Registrierung (bestehend)
    # -------------------------
    def get_user_count_by_email(self, email: str) -> int:
        query = "SELECT COUNT(*) FROM registrations WHERE email = %s"
        with self.conn.cursor() as cursor:
            cursor.execute(query, (email,))
            result = cursor.fetchone()
            return int(result[0]) if result else 0

    def insert_registration(self, firstname, lastname, email, school, minecraft_username, confirmed, created_at):
        query = """
            INSERT INTO registrations
            (firstname, lastname, email, school, minecraft_username, confirmed, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        with self.conn.cursor() as cursor:
            cursor.execute(query, (firstname, lastname, email, school, minecraft_username, confirmed, created_at))
        self.conn.commit()

    def delete_registration(self, email: str):
        query = "DELETE FROM registrations WHERE email = %s"
        with self.conn.cursor() as cursor:
            cursor.execute(query, (email,))
        self.conn.commit()

    def delete_registration_by_id(self, reg_id: int) -> int:
        """
        Löscht genau den Registration-Eintrag via ID.
        Gibt Anzahl gelöschter Rows zurück (0/1).
        """
        query = "DELETE FROM registrations WHERE id = %s"
        with self.conn.cursor() as cursor:
            cursor.execute(query, (reg_id,))
            self.conn.commit()
            return cursor.rowcount

    def confirm_registration(self, email: str):
        """
        ALT (nicht mehr für Confirm-Flow verwenden):
        Setzt confirmed=1 für ALLE Einträge dieser E-Mail.
        """
        query = "UPDATE registrations SET confirmed = 1 WHERE email = %s"
        with self.conn.cursor() as cursor:
            cursor.execute(query, (email,))
        self.conn.commit()

    def get_latest_minecraft_username(self, email: str):
        query = """
            SELECT minecraft_username
            FROM registrations
            WHERE email = %s
            ORDER BY created_at DESC
            LIMIT 1
        """
        with self.conn.cursor() as cursor:
            cursor.execute(query, (email,))
            result = cursor.fetchone()
            return result[0] if result else None

    def get_latest_firstname(self, email: str):
        query = """
            SELECT firstname
            FROM registrations
            WHERE email = %s
            ORDER BY created_at DESC
            LIMIT 1
        """
        with self.conn.cursor() as cursor:
            cursor.execute(query, (email,))
            result = cursor.fetchone()
            return result[0] if result else None

    def is_username_exists(self, minecraft_username: str) -> bool:
        try:
            if not self.conn or not self.conn.is_connected():
                raise RuntimeError("DB connection not active")

            query = "SELECT 1 FROM registrations WHERE minecraft_username = %s LIMIT 1"
            with self.conn.cursor() as cursor:
                cursor.execute(query, (minecraft_username,))
                return cursor.fetchone() is not None

        except Exception as e:
            logger.error(f"Fehler beim Überprüfen des Minecraft-Benutzernamens in der DB: {e}")
            return False

    # -------------------------
    # NEU: Atomare Bestätigung (wichtig!)
    # -------------------------
    def confirm_latest_unconfirmed_registration(self, email: str) -> dict | None:
        """
        Bestätigt GENAU den neuesten unbestätigten Eintrag (confirmed=0) für diese E-Mail.
        Erfolgreich nur, wenn:
          - ein passender Eintrag existiert
          - confirmed 0 -> 1 tatsächlich geändert wird (rowcount==1)

        Rückgabe bei Erfolg:
          {"id": ..., "firstname": ..., "minecraft_username": ...}
        Rückgabe bei Misserfolg:
          None
        """
        email = (email or "").strip()
        if not email:
            return None

        try:
            self.conn.start_transaction()

            # Wir holen exakt den Datensatz, den wir bestätigen wollen
            select_q = """
                SELECT id, firstname, minecraft_username
                FROM registrations
                WHERE email = %s AND confirmed = 0
                ORDER BY created_at DESC
                LIMIT 1
                FOR UPDATE
            """
            with self.conn.cursor(dictionary=True) as cursor:
                cursor.execute(select_q, (email,))
                row = cursor.fetchone()

            if not row:
                self.conn.rollback()
                return None

            update_q = "UPDATE registrations SET confirmed = 1 WHERE id = %s AND confirmed = 0"
            with self.conn.cursor() as cursor:
                cursor.execute(update_q, (row["id"],))
                if cursor.rowcount != 1:
                    self.conn.rollback()
                    return None

            self.conn.commit()
            return {
                "id": row["id"],
                "firstname": row.get("firstname"),
                "minecraft_username": row.get("minecraft_username"),
            }

        except Exception as e:
            try:
                self.conn.rollback()
            except Exception:
                pass
            logger.error(f"Fehler bei confirm_latest_unconfirmed_registration: {e}")
            return None

    def has_unconfirmed_registration(self, email: str) -> bool:
        """
        True, wenn es mindestens einen unbestätigten Eintrag für diese E-Mail gibt.
        """
        query = "SELECT 1 FROM registrations WHERE email = %s AND confirmed = 0 LIMIT 1"
        with self.conn.cursor() as cursor:
            cursor.execute(query, (email,))
            return cursor.fetchone() is not None

    # -------------------------
    # Whitelist (korrigiert: keine Duplikate)
    # -------------------------
    def insert_into_whitelist(self, uuid: str, username: str):
        """
        ALT: kann Duplikate erlauben (wenn keine Unique Constraints existieren).
        """
        try:
            query = "INSERT INTO mysql_whitelist (UUID, user) VALUES (%s, %s)"
            with self.conn.cursor() as cursor:
                cursor.execute(query, (uuid, username))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Fehler beim Eintragen in mysql_whitelist: {e}")

    def insert_into_whitelist_if_missing(self, uuid: str, username: str) -> str:
        """
        NEU: verhindert doppelte Einträge OHNE dass Unique Constraints zwingend vorhanden sind.
        Regel:
          - Wenn UUID ODER Username bereits existiert -> kein Insert, Rückgabe "already_exists"
          - Sonst Insert -> Rückgabe "inserted"
          - Bei Fehler -> "error"
        """
        uuid = (uuid or "").strip()
        username = (username or "").strip()
        if not uuid or not username:
            return "error"

        try:
            # Erst prüfen (uuid ODER username)
            exists_q = """
                SELECT 1
                FROM mysql_whitelist
                WHERE UUID = %s OR user = %s
                LIMIT 1
            """
            with self.conn.cursor() as cursor:
                cursor.execute(exists_q, (uuid, username))
                if cursor.fetchone() is not None:
                    return "already_exists"

            # Dann einfügen – zusätzlich abgesichert mit WHERE NOT EXISTS (Race-sicherer)
            insert_q = """
                INSERT INTO mysql_whitelist (UUID, user)
                SELECT %s, %s
                WHERE NOT EXISTS (
                    SELECT 1 FROM mysql_whitelist WHERE UUID = %s OR user = %s
                )
            """
            with self.conn.cursor() as cursor:
                cursor.execute(insert_q, (uuid, username, uuid, username))
                self.conn.commit()
                return "inserted" if cursor.rowcount == 1 else "already_exists"

        except Exception as e:
            logger.error(f"Fehler bei insert_into_whitelist_if_missing: {e}")
            return "error"

    # -------------------------
    # NEU: Sync removed whitelist -> registrations (bestehend)
    # -------------------------
    def get_whitelist_usernames(self) -> list[str]:
        """
        Liefert alle 'user' aus mysql_whitelist.
        """
        query = "SELECT user FROM mysql_whitelist"
        with self.conn.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()
            return [r[0] for r in rows if r and r[0]]

    def get_confirmed_registrations_basic(self) -> list[tuple[int, str, str]]:
        """
        Liefert bestätigte Registrierungen minimal:
          (id, email, minecraft_username)
        """
        query = """
            SELECT id, email, minecraft_username
            FROM registrations
            WHERE confirmed = 1
        """
        with self.conn.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall()

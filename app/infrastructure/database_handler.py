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
                host=self.config['db_host'],
                port=self.config['db_port'],
                user=self.config['db_user'],
                password=self.config['db_password'],
                database=self.config['db_database']
            )
            self.cursor = self.conn.cursor()
            logger.info("Verbindung zur Datenbank hergestellt.")
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

    def is_username_exists(self, minecraft_username: str) -> bool:
        try:
            if not self.conn or not self.conn.is_connected():
                raise RuntimeError("DB connection not active")

            query = "SELECT 1 FROM registrations WHERE minecraft_username = %s LIMIT 1"
            self.cursor.execute(query, (minecraft_username,))
            return self.cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Fehler beim Überprüfen des Minecraft-Benutzernamens in der DB: {e}")
            return False

    # -------------------------
    # Whitelist (bestehend)
    # -------------------------
    def insert_into_whitelist(self, uuid: str, username: str):
        try:
            query = "INSERT INTO mysql_whitelist (UUID, user) VALUES (%s, %s)"
            with self.conn.cursor() as cursor:
                cursor.execute(query, (uuid, username))
            self.conn.commit()
            logger.info(f"Spieler {username} mit UUID {uuid} erfolgreich in mysql_whitelist eingetragen.")
        except Exception as e:
            logger.error(f"Fehler beim Eintragen in mysql_whitelist: {e}")

    # -------------------------
    # NEU: Sync removed whitelist -> registrations
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

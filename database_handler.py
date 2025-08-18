import json
import mysql.connector
from datetime import datetime, timedelta
from log_handler import *

class DatabaseHandler:
    def __init__(self, config):
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
            logger.info(f"Fehler bei der Verbindung zur Datenbank: {error}")
            
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if self.cursor:
            self.cursor.close()
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
        except mysql.connector.Error as error:
            logger.info(f"Fehler beim Erstellen der Tabelle: {error}")
            raise error
        
    def get_unconfirmed_registrations_before(self, time_difference):
        query = """
            SELECT * FROM registrations WHERE confirmed = 0 AND created_at < %s
        """
        timestamp = datetime.now() - timedelta(minutes=time_difference)
        with self.conn.cursor() as cursor:
            cursor.execute(query, (timestamp,))
            return cursor.fetchall()

    def delete_unconfirmed_registrations_before(self, time_difference):
        query = """
            DELETE FROM registrations WHERE confirmed = 0 AND created_at < %s
        """
        timestamp = datetime.now() - timedelta(minutes=time_difference)
        with self.conn.cursor() as cursor:
            cursor.execute(query, (timestamp,))
            self.conn.commit()
            deleted_count = cursor.rowcount
            return deleted_count
        

    def get_user_count_by_email(self, email):
        query = "SELECT COUNT(*) FROM registrations WHERE email = %s"
        with self.conn.cursor() as cursor:
            cursor.execute(query, (email,))
            result = cursor.fetchone()
            if result:
                return result[0]
            return 0

    def insert_registration(self, firstname, lastname, email, school, minecraft_username, confirmed, created_at):
        query = "INSERT INTO registrations (firstname, lastname, email, school, minecraft_username, confirmed, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        with self.conn.cursor() as cursor:
            cursor.execute(query, (firstname, lastname, email, school, minecraft_username, confirmed, created_at))
        self.conn.commit()

    def delete_registration(self, email):
        query = "DELETE FROM registrations WHERE email = %s"
        with self.conn.cursor() as cursor:
            cursor.execute(query, (email,))
        self.conn.commit()

    def confirm_registration(self, email):
        query = "UPDATE registrations SET confirmed = 1 WHERE email = %s"
        with self.conn.cursor() as cursor:
            cursor.execute(query, (email,))
        self.conn.commit()

    def get_latest_minecraft_username(self, email):
        query = "SELECT minecraft_username FROM registrations WHERE email = %s ORDER BY created_at DESC LIMIT 1"
        with self.conn.cursor() as cursor:
            cursor.execute(query, (email,))
            result = cursor.fetchone()
            if result:
                return result[0]
            else:
                return None

    def is_username_exists(self, minecraft_username):
        try:
            if not self.conn.is_connected():
                self.__enter__()

            query = "SELECT * FROM registrations WHERE minecraft_username = %s"
            self.cursor.execute(query, (minecraft_username,))
            result = self.cursor.fetchone()

            if result:
                return True
            else:
                return False
        except Exception as e:
            logger.error("Fehler beim Überprüfen des Minecraft-Benutzernamens in der Datenbank: %s", str(e))
            return False

    def insert_into_whitelist(self, uuid, username):
        try:
            query = "INSERT INTO mysql_whitelist (UUID, user) VALUES (%s, %s)"
            with self.conn.cursor() as cursor:
                cursor.execute(query, (uuid, username))
            self.conn.commit()
            logger.info(f"Spieler {username} mit UUID {uuid} erfolgreich in mysql_whitelist eingetragen.")
        except Exception as e:
            logger.error(f"Fehler beim Eintragen in mysql_whitelist: {e}")

# Lade config.json.
with open('config.json') as file:
    config = json.load(file)

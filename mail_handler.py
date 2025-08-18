import json
import smtplib
import email.utils
from log_handler import *

def load_email_credentials() -> dict:
    logger.info("Lade E-Mail-Zugangsdaten aus JSON-Datei.")
    with open('config.json') as file:
        credentials = json.load(file)
        return credentials


def send_confirmation_email(to_email : str, confirmation_link : str):
    
    with open('config.json') as file:
        config = json.load(file)
        
    logger.info("Sende Bestätigungs-E-Mail.")
    parsed_email = email.utils.parseaddr(to_email)[1]  # to_email[1] enthält die E-Mail-Adresse
    email_credentials = load_email_credentials()

    # SMTP-Verbindung herstellen
    logger.info("Stelle SMTP-Verbindung her.")
    server = smtplib.SMTP(email_credentials['smtp_server'], email_credentials['smtp_port'])
    server.starttls()
    server.login(email_credentials['smtp_username'], email_credentials['smtp_password'])

    # E-Mail erstellen
    logger.info("Erstelle E-Mail.")
    subject = "Bestätigung der Registrierung"
    body = f"Hallo,\n\nBitte klicke auf den folgenden Link, um deine Registrierung zu bestätigen:\n{confirmation_link}\n\nVielen Dank!"
    message = f"Subject: {subject}\n\n{body}"

    # Debugging-Anweisungen
    if config['debug']:
        logger.info(f"Email: {parsed_email}")
        logger.info(f"Encoded Email: {parsed_email.encode('utf-8')}")
        logger.info(f"Message: {message}")
        logger.info(f"Encoded Message: {message.encode('utf-8')}")

    # E-Mail senden
    logger.info("Sende E-Mail.")
    server.sendmail(email_credentials['smtp_username'], parsed_email, message.encode('utf-8'))

    # SMTP-Verbindung beenden
    logger.info("Beende SMTP-Verbindung.")
    server.quit()
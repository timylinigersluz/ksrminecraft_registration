import sys, os, json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from log_handler import logger
from mail_handler import _connect_smtp, load_email_credentials
from email.utils import formataddr
from email.mime.text import MIMEText


def send_test_email():
    # Lade Konfigurationswerte
    with open('config.json') as file:
        config = json.load(file)

    creds = load_email_credentials()
    to_email = config.get("test_recipient", creds["smtp_username"])

    logger.info(f"Starte Test-E-Mail Versand an {to_email}")

    try:
        # Verbindung herstellen (automatische SSL/STARTTLS-Erkennung)
        server = _connect_smtp(creds)

        subject = "Testmail – KSR Minecraft"
        body = (
            "Hallo,\n\n"
            "Dies ist eine Testnachricht, um die SMTP-Credentials zu prüfen.\n\n"
            "Viele Grüsse,\nKSR Minecraft Bot"
        )

        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject

        # Anzeigename aus config.json
        sender_display_name = config.get("sender_display_name", "KSR Minecraft Team")
        msg["From"] = formataddr((sender_display_name, creds["smtp_username"]))

        msg["To"] = to_email

        # Mail senden
        server.sendmail(creds["smtp_username"], [to_email], msg.as_string())
        logger.info("✅ Testmail erfolgreich verschickt.")
        server.quit()
    except Exception as e:
        logger.error(f"❌ Fehler beim Senden der Testmail: {e}")


if __name__ == "__main__":
    send_test_email()

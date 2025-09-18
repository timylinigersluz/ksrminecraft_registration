import json
import smtplib
import email.utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from log_handler import *


def load_email_credentials() -> dict:
    logger.info("Lade E-Mail-Zugangsdaten aus JSON-Datei.")
    with open('config.json') as file:
        credentials = json.load(file)
        return credentials


def send_confirmation_email(to_email: str, confirmation_link: str, firstname: str = ""):
    """
    Sende eine Bestätigungs-E-Mail an den Benutzer.
    firstname: wird aus dem Formular übergeben (optional).
    """

    with open('config.json') as file:
        config = json.load(file)

    logger.info("Sende Bestätigungs-E-Mail.")
    parsed_email = email.utils.parseaddr(to_email)[1]
    email_credentials = load_email_credentials()

    # SMTP-Verbindung herstellen
    logger.info("Stelle SMTP-Verbindung her.")
    server = smtplib.SMTP(email_credentials['smtp_server'], email_credentials['smtp_port'])
    server.starttls()
    server.login(email_credentials['smtp_username'], email_credentials['smtp_password'])

    # Name für Anrede einsetzen
    greeting_name = firstname if firstname else "Spieler"

    # Betreff
    subject = Header("Bitte bestätige deine Registrierung bei KSR Minecraft", "utf-8")

    # Plaintext-Version (Fallback)
    text_body = f"""Hallo {greeting_name},

schön, dass du dich registriert hast! 🎉
Du bist schon fast am Ziel – es fehlt nur noch ein kleiner Schritt:

Bitte bestätige deine Registrierung über folgenden Link:
{confirmation_link}

Viele Grüsse vom KSR Minecraft Team  
Discord: https://discord.gg/ekmVqnzF9g ∙ Website: https://ksrminecraft.ch  

Bei Fragen melde dich ungeniert bei uns!
"""

    # HTML-Version (dein Layout, zentriert)
    html_body = f"""\
<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8">
    <title>KSR Minecraft Registrierung</title>
  </head>
  <body style="font-family: Arial, sans-serif; background-color: #f9f9f9; padding: 20px;">
    <div style="max-width: 600px; margin: auto; background: #ffffff; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); text-align: center;">
      
      <h2>Hallo {greeting_name},</h2>
      <p>schön, dass du dich registriert hast!</p>
      <p>Du bist schon fast am Ziel – es fehlt nur noch ein kleiner Schritt:</p>
      
      <!-- Link-Button -->
      <div style="margin: 20px 0;">
        <a href="{confirmation_link}"
           style="background: #28a745; color: #ffffff; padding: 12px 20px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block; margin: 10px 0;">
          Registrierung bestätigen
        </a><br>
      </div>

      <p>Viele Grüsse vom <strong>KSR Minecraft Team</strong></p>
      <p style="color: #555; font-size: 14px;">Bei Fragen melde dich ungeniert bei uns!</p>

      <!-- Logo -->
      <div style="margin-top: 30px;">
        <img src="https://ksrminecraft.ch/media/logos/logotransparentrechteck.png"
             alt="KSR Minecraft Logo" style="width:200px; opacity:0.8;">
      </div>

      <p>
        <a href="https://discord.gg/ekmVqnzF9g">Discord</a> ∙ 
        <a href="https://ksrminecraft.ch">Website</a>
      </p>
    </div>
  </body>
</html>
"""

    # Multipart-Mail (Plain + HTML)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr(("KSR Minecraft Team", email_credentials['smtp_username']))
    msg["To"] = parsed_email

    # Parts anhängen
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # Debugging
    if config['debug']:
        logger.info(f"Email: {parsed_email}")
        logger.info(f"Message (UTF-8): {msg.as_string()}")

    # Mail senden
    logger.info("Sende E-Mail.")
    server.sendmail(email_credentials['smtp_username'], [parsed_email], msg.as_string())

    # Verbindung beenden
    logger.info("Beende SMTP-Verbindung.")
    server.quit()

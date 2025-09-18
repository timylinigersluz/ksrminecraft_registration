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

schön, dass du dich registriert hast!
Du bist schon fast am Ziel – es fehlt nur noch ein kleiner Schritt:

{confirmation_link}

Viele Grüsse vom KSR Minecraft Team
Bei Fragen melde dich ungeniert bei uns!

Discord: https://discord.gg/ekmVqnzF9g
Website: https://ksrminecraft.ch
"""

    # HTML-Version (tabellenbasiert → für Outlook geeignet)
    html_body = f"""
    <html>
    <body style="margin:0; padding:0; background-color:#f9f9f9; font-family: Arial, sans-serif;">
      <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
        <tr>
          <td align="center" style="padding:20px 0;">
            <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="600" style="background:#ffffff; border-radius:8px;">
              <tr>
                <td align="center" style="padding:20px;">
                  <img src="https://ksrminecraft.ch/media/logos/logotransparentrechteck.png" alt="KSR Minecraft Logo" width="200" style="display:block; margin-bottom:20px;">
                </td>
              </tr>
              <tr>
                <td style="padding:0 30px; color:#333;">
                  <h2 style="text-align:center;">Hallo {greeting_name},</h2>
                  <p style="text-align:center;">schön, dass du dich registriert hast!</p>
                  <p style="text-align:center;">Du bist schon fast am Ziel – es fehlt nur noch ein kleiner Schritt:</p>
                </td>
              </tr>
              <tr>
                <td align="center" style="padding:30px;">
                  <table role="presentation" border="0" cellpadding="0" cellspacing="0">
                    <tr>
                      <td align="center" bgcolor="#28a745" style="border-radius:5px;">
                        <a href="{confirmation_link}" target="_blank" style="display:inline-block; padding:12px 20px; font-weight:bold; color:#ffffff; text-decoration:none; font-family: Arial, sans-serif;">
                          Registrierung bestätigen
                        </a>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
              <tr>
                <td style="padding:0 30px; text-align:center; color:#333;">
                  <p>Viele Grüsse vom <strong>KSR Minecraft Team</strong></p>
                  <p style="color:#555; font-size:14px;">Bei Fragen melde dich ungeniert bei uns!</p>
                </td>
              </tr>
              <tr>
                <td align="center" style="padding:20px; font-size:14px;">
                  <a href="https://discord.gg/ekmVqnzF9g" style="color:#007bff; text-decoration:none;">Discord</a> ∙ 
                  <a href="https://ksrminecraft.ch" style="color:#007bff; text-decoration:none;">Website</a>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
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

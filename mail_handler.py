import json
import smtplib
import ssl
import time
import imaplib
import email.utils

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr, formatdate, make_msgid

from log_handler import *


def load_email_credentials() -> dict:
    logger.info("Lade E-Mail-Zugangsdaten aus JSON-Datei.")
    with open('config.json', encoding="utf-8") as file:
        credentials = json.load(file)
        return credentials


def _connect_smtp(creds: dict):
    """
    Stellt je nach Port eine sichere SMTP-Verbindung her.
    - Port 465: SSL/TLS
    - Port 587: STARTTLS
    """
    server = None
    if creds["smtp_port"] == 465:
        logger.info("Verbinde per SMTP_SSL (Port 465).")
        server = smtplib.SMTP_SSL(creds["smtp_server"], creds["smtp_port"])
    elif creds["smtp_port"] == 587:
        logger.info("Verbinde per SMTP mit STARTTLS (Port 587).")
        server = smtplib.SMTP(creds["smtp_server"], creds["smtp_port"])
        server.ehlo()
        server.starttls(context=ssl.create_default_context())
        server.ehlo()
    else:
        logger.warning(f"Ungewohnter SMTP-Port {creds['smtp_port']} – versuche Standard-SMTP.")
        server = smtplib.SMTP(creds["smtp_server"], creds["smtp_port"])

    server.login(creds["smtp_username"], creds["smtp_password"])
    return server


def _is_inbox_namespace_error(data) -> bool:
    """
    Hosttech/Plesk liefert bei falschem Namespace oft:
    'Client tried to access nonexistent namespace. (Mailbox name should probably be prefixed with: INBOX.)'
    """
    if not data:
        return False

    blob = data[0] if isinstance(data, list) else data
    if isinstance(blob, bytes):
        return (b"prefixed with: INBOX" in blob) or (b"nonexistent namespace" in blob)

    return False


def _append_to_sent_imap(creds: dict, msg: MIMEMultipart, sent_folder: str):
    """
    Legt die gesendete Mail per IMAP in 'sent_folder' ab.
    Versucht bei Namespace-Problemen automatisch 'INBOX.<sent_folder>'.
    Gibt den effektiv verwendeten Ordner zurück (oder None bei Skip).
    """
    imap_host = creds.get("imap_server")
    imap_port = int(creds.get("imap_port", 993))

    if not imap_host:
        logger.warning("imap_server fehlt in config.json – Sent-Kopie wird nicht gespeichert.")
        return None

    user = creds["smtp_username"]
    pw = creds["smtp_password"]

    internal_date = imaplib.Time2Internaldate(time.time())

    imap = None
    try:
        imap = imaplib.IMAP4_SSL(imap_host, imap_port)
        imap.login(user, pw)

        # 1) erster Versuch
        status, data = imap.append(sent_folder, r"(\Seen)", internal_date, msg.as_bytes())
        logger.info(f"IMAP APPEND -> folder='{sent_folder}', status={status}, data={data}")

        # 2) Fallback: INBOX.<folder>
        if status != "OK" and _is_inbox_namespace_error(data) and not sent_folder.startswith("INBOX."):
            fallback = f"INBOX.{sent_folder}"
            status, data = imap.append(fallback, r"(\Seen)", internal_date, msg.as_bytes())
            logger.info(f"IMAP APPEND (fallback) -> folder='{fallback}', status={status}, data={data}")
            sent_folder = fallback

        if status != "OK":
            raise RuntimeError(f"IMAP APPEND fehlgeschlagen: {status} {data}")

        # Optional: Nachweis per Message-ID (hilft beim Debuggen)
        msgid = msg.get("Message-ID")
        if msgid:
            sel_status, _ = imap.select(sent_folder, readonly=True)
            logger.info(f"IMAP SELECT '{sent_folder}' -> {sel_status}")
            if sel_status == "OK":
                srch_status, hits = imap.search(None, f'(HEADER Message-ID "{msgid}")')
                logger.info(f"IMAP SEARCH Message-ID -> status={srch_status}, hits={hits}")

        return sent_folder

    finally:
        try:
            if imap:
                imap.logout()
        except Exception:
            pass


def send_confirmation_email(to_email: str, confirmation_link: str, firstname: str = ""):
    """
    Sende eine Bestätigungs-E-Mail an den Benutzer.
    firstname: wird aus dem Formular übergeben (optional).
    """

    with open('config.json', encoding="utf-8") as file:
        config = json.load(file)

    logger.info("Sende Bestätigungs-E-Mail.")
    parsed_email = email.utils.parseaddr(to_email)[1]
    email_credentials = load_email_credentials()

    # SMTP-Verbindung herstellen
    server = _connect_smtp(email_credentials)

    # Anzeigename aus config.json
    sender_display_name = config.get("sender_display_name", "KSR Minecraft Team")

    # Name für Anrede einsetzen
    greeting_name = firstname if firstname else "Spieler"

    # Betreff
    subject = Header("Bitte bestätige deine Registrierung bei KSR Minecraft", "utf-8")

    # Plaintext-Version (Fallback)
    text_body = f"""Hallo {greeting_name},

schön, dass du dich registriert hast!
Du bist schon fast am Ziel – es fehlt nur noch ein kleiner Schritt:

{confirmation_link}

Viele Grüsse vom {sender_display_name}
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
                  <p style="text-align:center;">Du bist schon fast am Ziel – es fehlt nur noch ein kleiner Schritt. Öffne bitte folgenden Link und bestätige deine Registrierung:</p>
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
                  <p>Viele Grüsse vom <strong>{sender_display_name}</strong></p>
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
    msg["From"] = formataddr((sender_display_name, email_credentials["smtp_username"]))
    msg["To"] = parsed_email

    # Hilft beim IMAP-Append/Debugging + saubere Mail-Metadaten
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()

    # Parts anhängen
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # Debugging
    if config.get("debug", False):
        logger.info(f"Email: {parsed_email}")
        logger.info(f"Message (UTF-8): {msg.as_string()}")

    # Mail senden + IMAP-Sent-Kopie
    try:
        logger.info("Sende E-Mail.")
        server.sendmail(email_credentials["smtp_username"], [parsed_email], msg.as_string())
        logger.info("✅ SMTP Versand OK")

        # Optional: Kopie in Sent speichern (IMAP)
        if config.get("imap_save_sent", False):
            sent_folder = config.get("sent_folder", "Sent")
            # IMAP-Server/Port können in config stehen (empfohlen),
            # wir reichen sie via creds mit.
            email_credentials["imap_server"] = config.get("imap_server", email_credentials.get("imap_server"))
            email_credentials["imap_port"] = config.get("imap_port", email_credentials.get("imap_port", 993))

            try:
                used_folder = _append_to_sent_imap(email_credentials, msg, sent_folder)
                if used_folder:
                    logger.info(f"✅ Sent-Kopie gespeichert in: '{used_folder}'")
            except Exception as e:
                # Wichtig: Versand soll nicht scheitern, nur weil Sent-Kopie nicht geht
                logger.error(f"Sent-Kopie per IMAP konnte nicht gespeichert werden: {e}")

    finally:
        logger.info("Beende SMTP-Verbindung.")
        try:
            server.quit()
        except Exception:
            pass

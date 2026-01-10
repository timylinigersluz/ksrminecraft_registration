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

from app.infrastructure.log_handler import logger


def load_email_credentials() -> dict:
    logger.info("Lade E-Mail-Zugangsdaten aus JSON-Datei.")
    with open("config.json", encoding="utf-8") as file:
        return json.load(file)


def _connect_smtp(creds: dict):
    """
    Stellt je nach Port eine sichere SMTP-Verbindung her.
    - Port 465: SSL/TLS
    - Port 587: STARTTLS
    """
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

        status, data = imap.append(sent_folder, r"(\Seen)", internal_date, msg.as_bytes())
        #logger.info(f"IMAP APPEND -> folder='{sent_folder}', status={status}, data={data}")

        if status != "OK" and _is_inbox_namespace_error(data) and not sent_folder.startswith("INBOX."):
            fallback = f"INBOX.{sent_folder}"
            status, data = imap.append(fallback, r"(\Seen)", internal_date, msg.as_bytes())
            logger.info(f"IMAP APPEND (fallback) -> folder='{fallback}', status={status}, data={data}")
            sent_folder = fallback

        if status != "OK":
            raise RuntimeError(f"IMAP APPEND fehlgeschlagen: {status} {data}")

        return sent_folder

    finally:
        try:
            if imap:
                imap.logout()
        except Exception:
            pass


def _send_email(
    *,
    to_email: str,
    subject_text: str,
    text_body: str,
    html_body: str | None,
    sender_display_name: str,
) -> None:
    """
    Generischer Mail-Sender (SMTP + optional IMAP Sent-Copy).
    """
    with open("config.json", encoding="utf-8") as file:
        config = json.load(file)

    email_credentials = load_email_credentials()
    parsed_email = email.utils.parseaddr(to_email)[1]

    server = _connect_smtp(email_credentials)

    subject = Header(subject_text, "utf-8")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((sender_display_name, email_credentials["smtp_username"]))
    msg["To"] = parsed_email

    # saubere Metadaten
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()

    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    if html_body:
        msg.attach(MIMEText(html_body, "html", "utf-8"))

    if config.get("debug"):
        logger.info(f"Email: {parsed_email}")
        logger.info(f"Message (UTF-8): {msg.as_string()}")

    logger.info("Sende E-Mail (SMTP).")
    server.sendmail(email_credentials["smtp_username"], [parsed_email], msg.as_string())

    # Optional: Sent speichern
    if config.get("imap_save_sent"):
        sent_folder = config.get("sent_folder", "Sent")
        try:
            _append_to_sent_imap(email_credentials, msg, sent_folder)
        except Exception as e:
            logger.error(f"Sent-Copy (IMAP) fehlgeschlagen: {e}")

    logger.info("Beende SMTP-Verbindung.")
    server.quit()


def send_confirmation_email(to_email: str, confirmation_link: str, firstname: str = ""):
    """
    Sende eine Bestätigungs-E-Mail an den Benutzer.
    """
    with open("config.json", encoding="utf-8") as file:
        config = json.load(file)

    sender_display_name = config.get("sender_display_name", "KSR Minecraft Team")
    greeting_name = firstname if firstname else "Spieler"

    subject_text = "Bitte bestätige deine Registrierung bei KSR Minecraft"

    text_body = f"""Hallo {greeting_name},

schön, dass du dich registriert hast!
Du bist schon fast am Ziel – es fehlt nur noch ein kleiner Schritt:

{confirmation_link}

Viele Grüsse vom {sender_display_name}
Bei Fragen melde dich ungeniert bei uns!

Discord: https://discord.gg/ekmVqnzF9g
Website: https://ksrminecraft.ch
"""

    # HTML (Outlook-kompatibel / tabellenbasiert)
    html_body = f"""
    <html>
    <body style="margin:0; padding:0; background-color:#f9f9f9; font-family: Arial, sans-serif;">
      <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
        <tr>
          <td align="center" style="padding:20px 0;">
            <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="600" style="background:#ffffff; border-radius:8px;">
              <tr>
                <td align="center" style="padding:20px;">
                  <img src="https://ksrminecraft.ch/assets/media/logos/logotransparentrechteck.png" alt="KSR Minecraft Logo" width="200" style="display:block; margin-bottom:20px;">
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

    logger.info("Sende Bestätigungs-E-Mail.")
    _send_email(
        to_email=to_email,
        subject_text=subject_text,
        text_body=text_body,
        html_body=html_body,
        sender_display_name=sender_display_name,
    )


def send_admin_alert_email(
    *,
    admin_email: str,
    user_email: str,
    firstname: str,
    lastname: str,
    school: str,
    minecraft_username: str,
    token: str,
    confirmation_link: str,
    error_message: str,
) -> None:
    """
    Benachrichtigt das Team, wenn der Versand an den User fehlgeschlagen ist.
    Enthält zusätzlich einen Bestätigungs-Button (Outlook-kompatibel).
    """
    with open("config.json", encoding="utf-8") as file:
        config = json.load(file)

    sender_display_name = config.get("sender_display_name", "KSR Minecraft Team")

    subject_text = f"[KSR Registration] Mailversand fehlgeschlagen ({minecraft_username})"

    text_body = f"""Hallo Team,

der Mailversand an den User ist fehlgeschlagen. Die Registrierung wurde bereits in der DB gespeichert.

Userdaten:
- Vorname: {firstname}
- Nachname: {lastname}
- E-Mail: {user_email}
- Schule: {school}
- Minecraft: {minecraft_username}

Fehler:
{error_message}

Token:
{token}

Bestätigungslink:
{confirmation_link}

Hinweis:
Der User wurde informiert, dass ihr euch meldet.
"""

    # Outlook-sicher: layout mit Tabellen + Button als <a> in <td bgcolor=...>
    html_body = f"""
    <html>
    <body style="margin:0; padding:0; background-color:#f6f6f6; font-family: Arial, sans-serif;">
      <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
        <tr>
          <td align="center" style="padding:20px 0;">
            <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="700" style="background:#ffffff; border-radius:10px;">
              <tr>
                <td style="padding:20px; border-bottom:1px solid #eee;">
                  <h2 style="margin:0; color:#333;">Mailversand fehlgeschlagen</h2>
                  <p style="margin:8px 0 0 0; color:#555;">
                    Die Registrierung wurde gespeichert, aber die Bestätigungs-E-Mail konnte nicht an den User gesendet werden.
                  </p>
                </td>
              </tr>

              <tr>
                <td style="padding:18px 20px; color:#333;">
                  <h3 style="margin:0 0 8px 0;">Userdaten</h3>
                  <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="border:1px solid #eee; border-radius:8px;">
                    <tr><td style="padding:10px; border-bottom:1px solid #eee;"><strong>Vorname:</strong> {firstname}</td></tr>
                    <tr><td style="padding:10px; border-bottom:1px solid #eee;"><strong>Nachname:</strong> {lastname}</td></tr>
                    <tr><td style="padding:10px; border-bottom:1px solid #eee;"><strong>E-Mail:</strong> {user_email}</td></tr>
                    <tr><td style="padding:10px; border-bottom:1px solid #eee;"><strong>Schule:</strong> {school}</td></tr>
                    <tr><td style="padding:10px;"><strong>Minecraft:</strong> {minecraft_username}</td></tr>
                  </table>

                  <h3 style="margin:16px 0 8px 0;">Fehler</h3>
                  <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="border:1px solid #eee; border-radius:8px;">
                    <tr>
                      <td style="padding:10px; background:#f3f3f3; color:#333; font-family: Consolas, Menlo, monospace; font-size: 13px; white-space: pre-wrap;">
                        {error_message}
                      </td>
                    </tr>
                  </table>

                  <h3 style="margin:16px 0 8px 0;">Token</h3>
                  <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="border:1px solid #eee; border-radius:8px;">
                    <tr>
                      <td style="padding:10px; background:#f3f3f3; color:#333; font-family: Consolas, Menlo, monospace; font-size: 13px; white-space: pre-wrap;">
                        {token}
                      </td>
                    </tr>
                  </table>

                  <h3 style="margin:16px 0 8px 0;">Bestätigungslink</h3>
                  <p style="margin:0 0 10px 0;">
                    <a href="{confirmation_link}" target="_blank" style="color:#007bff; text-decoration:none;">
                      {confirmation_link}
                    </a>
                  </p>
                </td>
              </tr>

              <!-- Button -->
              <tr>
                <td align="center" style="padding:10px 20px 24px;">
                  <table role="presentation" border="0" cellpadding="0" cellspacing="0">
                    <tr>
                      <td align="center" bgcolor="#28a745" style="border-radius:6px;">
                        <a href="{confirmation_link}" target="_blank"
                           style="display:inline-block; padding:12px 22px; font-weight:bold; color:#ffffff; text-decoration:none; font-family: Arial, sans-serif;">
                          Registrierung bestätigen
                        </a>
                      </td>
                    </tr>
                  </table>
                  <p style="margin:12px 0 0 0; color:#777; font-size: 12px;">
                    (öffnet den Bestätigungslink in einem Browser)
                  </p>
                </td>
              </tr>

              <tr>
                <td style="padding:14px 20px; background:#fafafa; border-top:1px solid #eee; color:#777; font-size:12px;">
                  Hinweis: Der User wurde informiert, dass ihr euch meldet.
                </td>
              </tr>

            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """

    logger.info(f"Sende Admin-Alert an {admin_email}.")
    _send_email(
        to_email=admin_email,
        subject_text=subject_text,
        text_body=text_body,
        html_body=html_body,
        sender_display_name=sender_display_name,
    )

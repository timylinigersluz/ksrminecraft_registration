from __future__ import annotations

import json
import time
import imaplib
import smtplib
import email.utils
from pathlib import Path
from typing import Any, Dict, Optional
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.infrastructure.log_handler import logger


# ------------------------------------------------------------
# Config laden (CWD-unabhängig)
# ------------------------------------------------------------
def _project_root() -> Path:
    # .../app/infrastructure/mail_handler.py -> parents: [infrastructure, app, projectroot]
    return Path(__file__).resolve().parents[2]


def load_config(config_path: str | Path = "config.json") -> Dict[str, Any]:
    path = Path(config_path)
    if not path.is_absolute():
        path = _project_root() / path

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------
# Jinja Environment für Templates (ohne Flask-Kontext)
# ------------------------------------------------------------
_JINJA_ENV: Optional[Environment] = None


def _get_jinja_env() -> Environment:
    global _JINJA_ENV
    if _JINJA_ENV is not None:
        return _JINJA_ENV

    templates_dir = _project_root() / "app" / "templates"
    _JINJA_ENV = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    return _JINJA_ENV


def render_email_template(template_name: str, context: Dict[str, Any]) -> str:
    env = _get_jinja_env()
    template = env.get_template(template_name)
    return template.render(**context)


# ------------------------------------------------------------
# SMTP Verbindung
# ------------------------------------------------------------
def _connect_smtp(cfg: Dict[str, Any]) -> smtplib.SMTP:
    smtp_server = cfg["smtp_server"]
    smtp_port = int(cfg["smtp_port"])
    smtp_username = cfg["smtp_username"]
    smtp_password = cfg["smtp_password"]

    server: smtplib.SMTP

    if smtp_port == 465:
        logger.info("Verbinde per SMTP_SSL (Port 465).")
        server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=15)
    elif smtp_port == 587:
        logger.info("Verbinde per SMTP mit STARTTLS (Port 587).")
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=15)
        server.ehlo()
        server.starttls()
        server.ehlo()
    else:
        logger.warning(f"Ungewohnter SMTP-Port {smtp_port} – versuche Standard-SMTP.")
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=15)

    server.login(smtp_username, smtp_password)
    return server


# ------------------------------------------------------------
# IMAP: "Sent" finden und Mail anhängen (optional)
# ------------------------------------------------------------
def _imap_connect(cfg: Dict[str, Any]) -> imaplib.IMAP4_SSL:
    imap_server = cfg.get("imap_server") or cfg.get("smtp_server")
    imap_port = int(cfg.get("imap_port", 993))

    username = cfg.get("imap_username") or cfg["smtp_username"]
    password = cfg.get("imap_password") or cfg["smtp_password"]

    logger.info(f"Verbinde per IMAP_SSL: {imap_server}:{imap_port}")
    imap = imaplib.IMAP4_SSL(imap_server, imap_port)
    imap.login(username, password)
    return imap


def _list_mailboxes(imap: imaplib.IMAP4_SSL) -> list[str]:
    status, data = imap.list()
    if status != "OK" or not data:
        return []
    names: list[str] = []
    for line in data:
        if not line:
            continue
        s = line.decode(errors="ignore")
        if '"' in s:
            names.append(s.split('"')[-2])
        else:
            names.append(s.split()[-1])
    return names


def _resolve_sent_mailbox(imap: imaplib.IMAP4_SSL, sent_folder: str) -> str:
    wanted = (sent_folder or "Sent").strip()
    wanted_lc = wanted.lower()

    boxes = _list_mailboxes(imap)

    for b in boxes:
        if b == wanted:
            return b
    for b in boxes:
        if b.lower() == wanted_lc:
            return b

    for candidate in (f"INBOX.{wanted}", f"INBOX/{wanted}", f"INBOX.{wanted_lc}", f"INBOX/{wanted_lc}"):
        for b in boxes:
            if b == candidate or b.lower() == candidate.lower():
                return b

    return wanted


def _append_to_sent(cfg: Dict[str, Any], msg: MIMEMultipart) -> None:
    if not cfg.get("imap_save_sent", False):
        return

    sent_folder_cfg = cfg.get("sent_folder", "Sent")

    imap: Optional[imaplib.IMAP4_SSL] = None
    try:
        imap = _imap_connect(cfg)
        sent_box = _resolve_sent_mailbox(imap, sent_folder_cfg)

        internal_date = imaplib.Time2Internaldate(time.time())

        status, data = imap.append(sent_box, r"(\Seen)", internal_date, msg.as_bytes())
        logger.info(f"IMAP APPEND -> folder='{sent_box}', status={status}, data={data}")

        if status != "OK":
            retry_box = f"INBOX.{sent_box}" if not sent_box.upper().startswith("INBOX.") else sent_box
            if retry_box != sent_box:
                status2, data2 = imap.append(retry_box, r"(\Seen)", internal_date, msg.as_bytes())
                logger.info(f"IMAP APPEND RETRY -> folder='{retry_box}', status={status2}, data={data2}")

    except Exception as e:
        logger.warning(f"IMAP APPEND (Sent) fehlgeschlagen: {e}")

    finally:
        try:
            if imap:
                imap.logout()
        except Exception:
            pass


# ------------------------------------------------------------
# Public API: Bestätigungs-Mail senden
# ------------------------------------------------------------
def send_confirmation_email(
    to_email: str,
    confirmation_link: str,
    firstname: str = "",
    *,
    cfg: Optional[Dict[str, Any]] = None,
):
    """
    Sende eine Bestätigungs-E-Mail an den Benutzer.
    - HTML kommt aus app/templates/mail_preview.html (Jinja)
    - Plaintext bleibt als Fallback
    - optional: Kopie in Sent via IMAP APPEND (imap_save_sent=true)
    """
    config = cfg or load_config("config.json")

    parsed_email = email.utils.parseaddr(to_email)[1]
    sender_display_name = config.get("sender_display_name", "KSR Minecraft Team")
    greeting_name = firstname if firstname else "Spieler"

    subject = Header("Bitte bestätige deine Registrierung bei KSR Minecraft", "utf-8")

    # Plaintext fallback
    text_body = f"""Hallo {greeting_name},

schön, dass du dich registriert hast!
Du bist schon fast am Ziel – es fehlt nur noch ein kleiner Schritt:

{confirmation_link}

Viele Grüsse vom {sender_display_name}
Bei Fragen melde dich ungeniert bei uns!

Discord: https://discord.gg/ekmVqnzF9g
Website: https://ksrminecraft.ch
"""

    # HTML via Template
    html_body = render_email_template(
        "mail_preview.html",
        {
            "greeting_name": greeting_name,
            "confirmation_link": confirmation_link,
            "sender_display_name": sender_display_name,
            "discord_url": "https://discord.gg/ekmVqnzF9g",
            "website_url": "https://ksrminecraft.ch",
            "logo_url": "https://ksrminecraft.ch/media/logos/logotransparentrechteck.png",
        },
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((sender_display_name, config["smtp_username"]))
    msg["To"] = parsed_email

    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    if config.get("debug", False):
        logger.info(f"Email: {parsed_email}")
        logger.info("Message (UTF-8) erstellt (gekürzt).")

    server: Optional[smtplib.SMTP] = None
    try:
        server = _connect_smtp(config)
        logger.info("Sende E-Mail (SMTP).")
        server.sendmail(config["smtp_username"], [parsed_email], msg.as_string())
    finally:
        try:
            if server:
                server.quit()
        except Exception:
            pass

    # optional: Kopie in Sent speichern
    _append_to_sent(config, msg)

    logger.info("E-Mail Versand abgeschlossen.")

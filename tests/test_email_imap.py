# tests/test_email_imap.py
import json
import smtplib
import ssl
import imaplib
import time
from datetime import datetime

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr, formatdate, make_msgid


def load_config(path="config.json") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def connect_smtp(cfg: dict):
    host = cfg["smtp_server"]
    port = int(cfg["smtp_port"])
    user = cfg["smtp_username"]
    pw = cfg["smtp_password"]

    if port == 465:
        server = smtplib.SMTP_SSL(host, port)
    elif port == 587:
        server = smtplib.SMTP(host, port)
        server.ehlo()
        server.starttls(context=ssl.create_default_context())
        server.ehlo()
    else:
        server = smtplib.SMTP(host, port)

    server.login(user, pw)
    return server


def build_test_message(cfg: dict, to_email: str) -> MIMEMultipart:
    sender_name = cfg.get("sender_display_name", cfg["smtp_username"])
    from_addr = cfg["smtp_username"]

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    subject = Header(f"TESTMAIL ({now})", "utf-8")

    text_body = (
        "Hallo!\n\n"
        "Das ist eine Testmail aus dem Python-Testskript.\n"
        f"Zeit: {now}\n\n"
        f"Viele Grüsse\n{sender_name}\n"
    )

    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif;">
        <h2>✅ Testmail</h2>
        <p>Das ist eine Testmail aus dem Python-Testskript.</p>
        <p><strong>Zeit:</strong> {now}</p>
        <p>Viele Grüsse<br><strong>{sender_name}</strong></p>
      </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((sender_name, from_addr))
    msg["To"] = to_email
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()

    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    return msg


def append_to_sent(cfg: dict, msg: MIMEMultipart):
    """
    Speichert die gesendete Nachricht zusätzlich in den IMAP-Ordner 'sent_folder'.

    Wichtige config keys:
      - imap_server (z.B. cap.ssl.hosttech.eu)
      - imap_port (typisch 993)
      - sent_folder (bei dir: INBOX.Sent)
    """
    imap_host = cfg["imap_server"]
    imap_port = int(cfg.get("imap_port", 993))
    user = cfg["smtp_username"]
    pw = cfg["smtp_password"]

    # Bei deinem Server muss es INBOX.Sent sein (Namespace verlangt Prefix INBOX.)
    sent_folder = cfg.get("sent_folder", "INBOX.Sent")

    imap = imaplib.IMAP4_SSL(imap_host, imap_port)
    imap.login(user, pw)

    internal_date = imaplib.Time2Internaldate(time.time())

    status, data = imap.append(sent_folder, r"(\Seen)", internal_date, msg.as_bytes())
    print(f"IMAP APPEND -> folder='{sent_folder}', status={status}, data={data}")

    if status != "OK":
        imap.logout()
        raise RuntimeError(f"IMAP APPEND fehlgeschlagen: {status} {data}")

    # Optional: Kurz prüfen, ob die Mail im Ordner auffindbar ist (Message-ID)
    msgid = msg.get("Message-ID")
    if msgid:
        sel_status, _ = imap.select(sent_folder, readonly=True)
        print(f"IMAP SELECT '{sent_folder}' -> {sel_status}")
        if sel_status == "OK":
            srch_status, hits = imap.search(None, f'(HEADER Message-ID "{msgid}")')
            print(f"IMAP SEARCH Message-ID -> status={srch_status}, hits={hits}")

    imap.logout()


def main():
    cfg = load_config()

    # Empfänger: test_recipient, sonst an dich selbst
    to_email = cfg.get("test_recipient", cfg["smtp_username"])

    msg = build_test_message(cfg, to_email)

    print(f"Sende Testmail an: {to_email} via {cfg['smtp_server']}:{cfg['smtp_port']} ...")
    smtp = connect_smtp(cfg)
    smtp.sendmail(cfg["smtp_username"], [to_email], msg.as_string())
    smtp.quit()
    print("✅ SMTP Versand OK")

    if cfg.get("imap_save_sent", True):
        append_to_sent(cfg, msg)
        print(f"✅ Kopie in Sent gespeichert (sent_folder='{cfg.get('sent_folder', 'INBOX.Sent')}')")
    else:
        print("ℹ️ imap_save_sent=false → keine Kopie in Sent gespeichert")

    print("Fertig.")


if __name__ == "__main__":
    main()

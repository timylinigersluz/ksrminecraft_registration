# Main-File für die Registrierung von Benutzern für den Minecraft-Server
from flask import Flask, render_template, request, redirect, url_for
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from log_handler import *
from database_handler import DatabaseHandler
import json, mail_handler, datetime, time, threading, signal, sys
import mojang_handler  # neue Datei für Mojang-Username/UUID-Check

app = Flask(__name__, template_folder='templates')

# Laden der Konfiguration
with open('config.json') as file:
    config = json.load(file)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/success')
def success():
    return render_template('success.html', config=config)


@app.route('/registration_completed')
def registration_completed():
    return render_template('registration_completed.html', config=config)


@app.route('/error')
def error():
    errors = request.args.get('errors')
    return render_template('error.html', errors=errors)


@app.route('/register', methods=['GET'])
def show_registration_form():
    return render_template('registration.html')


# SECRET_KEY aus JSON-Datei laden
def load_secret_key():
    with open('secret_key.json') as file:
        data = json.load(file)
        logger.info("Json-Secret-File erfolgreich geladen.")
        return data['secret_key']


# Laden der SECRET_KEY aus der JSON-Datei
app.config['SECRET_KEY'] = load_secret_key()
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
logger.info("Json-Secret-File erfolgreich inizialisiert.")


# Registrierungsdaten verarbeiten
@app.route('/register', methods=['POST'])
def register():
    logger.info("Versuche neuen User zu registrieren.")
    firstname = request.form['firstname']
    lastname = request.form['lastname']
    email = request.form['email']
    school = request.form['school']
    minecraft_username = request.form['minecraft_username']

    errors = []

    # Validierung der Eingabedaten
    if not firstname:
        errors.append('Vorname ist erforderlich.')
    if not lastname:
        errors.append('Nachname ist erforderlich.')
    if not email:
        errors.append('E-Mail ist erforderlich.')
    if not school:
        errors.append('Schule ist erforderlich.')
    if not minecraft_username:
        errors.append('Minecraft-Benutzername ist erforderlich.')

    if errors:
        return render_template('error.html', errors=errors)

    with DatabaseHandler(config) as db:
        count = db.get_user_count_by_email(email)
        max_permitted_users_per_mail = config['max_users_per_mail']

    # E-Mail-Endung prüfen
    accepted_mail_endings = config['accepted_mail_endings']
    if not any(email.endswith(ending) for ending in accepted_mail_endings):
        logger.info("Abbruch: Unzulässige Mailendung.")
        return render_template('error.html', errors=['Die Registrierung ist nur für bestimmte Maildomains erlaubt.'])

    # Zu viele Accounts pro Mail?
    if count >= max_permitted_users_per_mail:
        logger.info(f"Abbruch: Zu viele User mit dieser E-Mail-Adresse registriert ({email})")
        return render_template('error.html', errors=[f"Es sind bereits {max_permitted_users_per_mail} Benutzer mit dieser E-Mail-Adresse registriert."])

    # Benutzername schon registriert?
    with DatabaseHandler(config) as db:
        if db.is_username_exists(minecraft_username):
            logger.info(f"Abbruch: Benutzername bereits in der Datenbank vorhanden ({minecraft_username}).")
            return render_template('error.html', errors=['Dieser Minecraft-Benutzername ist bereits registriert.'])

    # Offizieller Minecraft-Account?
    if not mojang_handler.is_official_username(minecraft_username):
        logger.info(f"Abbruch: Kein gültiger Minecraft-Account ({minecraft_username}).")
        return render_template('error.html', errors=['Ungültiger Minecraft-Benutzername.'])

    # Token generieren
    logger.info("Generiere Token für Bestätigungslink.")
    token = serializer.dumps(email, salt='email-confirm')

    # Registrierung speichern
    logger.info("Speichere Registrierungsdaten in Datenbank.")
    created_at = datetime.datetime.now()
    with DatabaseHandler(config) as db:
        db.insert_registration(firstname, lastname, email, school, minecraft_username, 0, created_at)

    # Bestätigungslink (führt auf confirm_page!)
    confirmation_link = request.host_url + 'confirm_page/' + token
    logger.info(f"Sende Bestätigungslink mit Token ({token}) per E-Mail.")
    mail_handler.send_confirmation_email(to_email=email, confirmation_link=confirmation_link, firstname=firstname)

    logger.info("Registrierung erfolgreich abgeschlossen.")
    return redirect(url_for('success'))


# Zwischenseite anzeigen
@app.route('/confirm_page/<token>', methods=['GET'])
def confirm_page(token):
    try:
        email = serializer.loads(token, salt='email-confirm', max_age=config['waiting_time_for_db_cleaner'] * 600)
        return render_template('confirm_page.html', email=email, token=token)
    except SignatureExpired:
        logger.info("Bestätigungslink abgelaufen (Zwischenseite).")
        return render_template('error.html', errors=['Bestätigungslink ist abgelaufen.'])
    except BadSignature:
        logger.info("Ungültiger Bestätigungslink (Zwischenseite).")
        return render_template('error.html', errors=['Ungültiger Bestätigungslink.'])
    except Exception as e:
        logger.info(f"Fehler beim Laden der Zwischenseite: {e}")
        return render_template('error.html', errors=['Fehler beim Laden der Bestätigungsseite.'])


# Bestätigung per Button-Klick (POST)
@app.route('/confirm', methods=['POST'])
def confirm_email():
    token = request.form.get('token')
    try:
        logger.info("Versuche Bestätigungsemail zu verarbeiten.")
        email = serializer.loads(token, salt='email-confirm', max_age=config['waiting_time_for_db_cleaner'] * 600)

        # Registrierungsstatus setzen
        logger.info("Aktualisiere Bestätigungsstatus in Datenbank.")
        with DatabaseHandler(config) as db:
            db.confirm_registration(email)

        # Benutzernamen abrufen
        with DatabaseHandler(config) as db:
            minecraft_username = db.get_latest_minecraft_username(email)

        if minecraft_username:
            uuid = mojang_handler.get_uuid(minecraft_username)
            if uuid:
                with DatabaseHandler(config) as db:
                    db.insert_into_whitelist(uuid, minecraft_username)
                logger.info("Bestätigung erfolgreich abgeschlossen und Spieler in mysql_whitelist eingetragen.")
            else:
                logger.error(f"Keine UUID für {minecraft_username} gefunden – Spieler NICHT eingetragen!")

            return redirect(url_for('registration_completed'))
        else:
            logger.info("Kein Benutzername in der DB gefunden.")
            return render_template('error.html', errors=[f'Der Minecraft-Benutzername für {email} konnte nicht gefunden werden.'])

    except SignatureExpired:
        logger.info("Bestätigungslink abgelaufen.")
        return render_template('error.html', errors=['Bestätigungslink ist abgelaufen.'])
    except BadSignature:
        logger.info("Ungültiger Bestätigungslink.")
        return render_template('error.html', errors=['Ungültiger Bestätigungslink.'])
    except Exception as e:
        logger.info(f"Fehler beim Bestätigen: {e}")
        return render_template('error.html', errors=['Fehler beim Bestätigen der Registrierung.'])


# Cleanup-Handler
def cleanup_handler(signum, frame):
    logger.info("Datenbank-Cleaner beendet.")
    sys.exit(0)


# Unbestätigte Registrierungen bereinigen
def cleanup_unconfirmed_registrations():
    while True:
        try:
            logger.info("Starte Datenbank-Cleaner.")
            time_difference = config['waiting_time_for_db_cleaner']
            with DatabaseHandler(config) as db_handler:
                unconfirmed = db_handler.get_unconfirmed_registrations_before(time_difference)
                deleted_count = db_handler.delete_unconfirmed_registrations_before(time_difference)

            if deleted_count > 0:
                logger.info(f"{deleted_count} Einträge wurden gelöscht:")
                for reg in unconfirmed:
                    email = reg[3]
                    minecraft_username = reg[5]
                    logger.info(f"Email: {email}, Minecraft-Benutzername: {minecraft_username}")
            else:
                logger.info("Es wurden keine Einträge gelöscht.")

            time.sleep(time_difference * 60)
        except Exception as e:
            logger.error(f"Fehler beim Bereinigen der unbestätigten Registrierungen: {e}")
            time.sleep(30)


# Factory-Methode für Gunicorn
def init_app():
    logger.info("Initialisiere App (DB + Cleaner).")
    with DatabaseHandler(config) as db_handler:
        db_handler.create_table()

    cleanup_thread = threading.Thread(target=cleanup_unconfirmed_registrations)
    cleanup_thread.daemon = True
    cleanup_thread.start()
    logger.info("Cleanup-Thread gestartet.")

    return app


# Gunicorn braucht 'application'
application = init_app()

# Nur im DEV-Modus direkt starten
if __name__ == '__main__':
    logger.info("Starte Webserver im DEV-Modus.")
    signal.signal(signal.SIGTERM, cleanup_handler)
    app.run(host="127.0.0.1", port=5000, debug=config['debug'])

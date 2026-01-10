# app/routes/registration_routes.py

from __future__ import annotations

from flask import (
    Blueprint,
    current_app,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
)

from app.services.registration_service import process_registration

registration_bp = Blueprint("registration", __name__)


def _wants_json_response() -> bool:
    """
    Erkennung: kommt der Request via fetch/AJAX?
    - Wir setzen im script.js bewusst 'X-Requested-With: fetch'
    - Zusätzlich akzeptieren wir JSON über Accept-Header
    """
    xrw = (request.headers.get("X-Requested-With") or "").lower()
    if xrw == "fetch":
        return True

    accept = (request.headers.get("Accept") or "").lower()
    return "application/json" in accept


def _safe_form_value(key: str) -> str:
    return (request.form.get(key) or "").strip()


@registration_bp.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@registration_bp.route("/success", methods=["GET"])
def success():
    cfg = current_app.config["APP_CONFIG"]

    # Werte kommen via Querystring vom Redirect (oder sind leer im Preview)
    email = (request.args.get("email") or "").strip()
    firstname = (request.args.get("firstname") or "").strip()

    return render_template(
        "success.html",
        config=cfg,
        email=email,
        firstname=firstname,
    )


@registration_bp.route("/registration_completed", methods=["GET"])
def registration_completed():
    cfg = current_app.config["APP_CONFIG"]
    return render_template("registration_completed.html", config=cfg)


@registration_bp.route("/error", methods=["GET"])
def error():
    # Querystring-Variante (optional)
    errors = request.args.get("errors")
    return render_template("error.html", errors=errors)


@registration_bp.route("/register", methods=["GET"])
def show_registration_form():
    return render_template("registration.html")


# --- CORS Preflight für embedded fetch() ---
@registration_bp.route("/register", methods=["OPTIONS"])
def register_options():
    # CORS-Header werden in app.after_request gesetzt (app/__init__.py).
    # Wir müssen nur 204 zurückgeben.
    return ("", 204)


@registration_bp.route("/register", methods=["POST"])
def register():
    cfg = current_app.config["APP_CONFIG"]
    serializer = current_app.config["SERIALIZER"]

    # Für success-Page: diese Daten wollen wir durchreichen (auch im OK-Fall)
    firstname = _safe_form_value("firstname")
    email = _safe_form_value("email")

    result = process_registration(
        form=request.form,
        config=cfg,
        serializer=serializer,
        request_host_url=request.host_url,
    )

    # --- JSON-Antwort (für Embedded-Formular / fetch) ---
    if _wants_json_response():
        if not result.get("ok"):
            errors = result.get("errors") or ["Unbekannter Fehler."]
            return (
                jsonify(
                    ok=False,
                    errors=errors,
                    message=" | ".join(errors),
                ),
                400,
            )

        # ok: Wir geben eine URL mit, falls du im Frontend optional weiterleiten willst
        redirect_url = url_for(
            "registration.success",
            email=email,
            firstname=firstname,
            _external=True,
        )

        return (
            jsonify(
                ok=True,
                message="Erfolgreich gesendet.\nPrüfe in 2 Minuten dein Postfach (auch Spam).",
                redirect_url=redirect_url,
            ),
            200,
        )

    # --- HTML/Browser-Flow (klassisches POST -> Redirect/Template) ---
    if not result.get("ok"):
        return render_template("error.html", errors=result.get("errors", ["Unbekannter Fehler."]))

    return redirect(url_for("registration.success", email=email, firstname=firstname))

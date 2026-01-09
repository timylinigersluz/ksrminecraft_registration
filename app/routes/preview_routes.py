# app/routes/preview_routes.py

from __future__ import annotations

from flask import Blueprint, render_template, request, current_app


preview_bp = Blueprint("preview", __name__)

LOGO_URL = "https://ksrminecraft.ch/assets/media/logos/logotransparentrechteck.png"
DISCORD_URL = "https://discord.gg/ekmVqnzF9g"
WEBSITE_URL = "https://ksrminecraft.ch"


def _cfg() -> dict:
    return current_app.config.get("APP_CONFIG", {}) or {}


@preview_bp.route("/preview", methods=["GET"])
def preview_root():
    """
    Mini-Übersicht aller Preview-Routen.
    """
    return (
        "<h2>Preview-Routen</h2>"
        "<ul>"
        "<li><a href='/preview/index'>/preview/index</a></li>"
        "<li><a href='/preview/registration'>/preview/registration</a></li>"
        "<li><a href='/preview/success'>/preview/success</a></li>"
        "<li><a href='/preview/registration_completed'>/preview/registration_completed</a></li>"
        "<li><a href='/preview/error'>/preview/error</a></li>"
        "<li><a href='/preview/confirm_page'>/preview/confirm_page</a></li>"
        "<li><a href='/preview/mail_preview'>/preview/mail_preview</a></li>"
        "</ul>"
    )


@preview_bp.route("/preview/index", methods=["GET"])
def preview_index():
    return render_template("index.html", config=_cfg())


@preview_bp.route("/preview/registration", methods=["GET"])
def preview_registration():
    return render_template("registration.html", config=_cfg())


@preview_bp.route("/preview/success", methods=["GET"])
def preview_success():
    return render_template("success.html", config=_cfg())


@preview_bp.route("/preview/registration_completed", methods=["GET"])
def preview_registration_completed():
    return render_template("registration_completed.html", config=_cfg())


@preview_bp.route("/preview/error", methods=["GET"])
def preview_error():
    """
    Beispiel:
      /preview/error
      /preview/error?errors=Fehler%201|Fehler%202
    """
    raw = request.args.get("errors", "Beispiel-Fehler 1|Beispiel-Fehler 2")
    errors = [e.strip() for e in raw.split("|") if e.strip()]
    return render_template("error.html", errors=errors)


@preview_bp.route("/preview/confirm_page", methods=["GET"])
def preview_confirm_page():
    """
    Beispiel:
      /preview/confirm_page
      /preview/confirm_page?email=test@sluz.ch&token=ABC123
    """
    email = request.args.get("email", "test@sluz.ch")
    token = request.args.get("token", "DEMO_TOKEN")
    return render_template("confirm_page.html", email=email, token=token)


@preview_bp.route("/preview/mail_preview", methods=["GET"])
def preview_mail_preview():
    """
    Beispiel:
      /preview/mail_preview
      /preview/mail_preview?name=Timy
      /preview/mail_preview?name=Timy&link=https://example.com
    """
    cfg = _cfg()

    greeting_name = request.args.get("name", "Spieler")
    confirmation_link = request.args.get(
        "link",
        request.host_url.rstrip("/") + "/confirm_page/DEMO_TOKEN"
    )

    context = {
        "greeting_name": greeting_name,
        "confirmation_link": confirmation_link,
        "sender_display_name": cfg.get("sender_display_name", "KSR Minecraft Team"),
        "discord_url": DISCORD_URL,
        "website_url": WEBSITE_URL,
        "logo_url": LOGO_URL,
        "config": cfg,
    }

    return render_template("mail_preview.html", **context)

# app/policies/email_policy.py

from __future__ import annotations

from typing import Dict


def normalize_email(value: str) -> str:
    """
    Normalisiert E-Mail für Vergleiche (case-insensitive).
    """
    return (value or "").strip().lower()


def get_email_user_limits_map(cfg: dict) -> Dict[str, int]:
    """
    Liefert email_user_limits als normalisierte Map:
      { "mail@domain.tld": int_limit, ... }

    Ungültige Einträge werden ignoriert.
    """
    raw = cfg.get("email_user_limits", {}) or {}
    normalized: Dict[str, int] = {}

    for k, v in raw.items():
        key = normalize_email(str(k))
        try:
            normalized[key] = int(v)
        except Exception:
            # Falls jemand Mist einträgt, ignorieren wir den Eintrag
            continue

    return normalized


def is_email_allowed(email: str, cfg: dict) -> bool:
    """
    Erlaubt sind:
      - E-Mails, deren Endung in accepted_mail_endings vorkommt
      - ODER E-Mails, die explizit in email_user_limits stehen
        (auch wenn Endung nicht erlaubt wäre)
    """
    email_lc = normalize_email(email)

    # Whitelist/Override via email_user_limits
    limits = get_email_user_limits_map(cfg)
    if email_lc in limits:
        return True

    accepted_mail_endings = cfg.get("accepted_mail_endings", []) or []
    return any(email_lc.endswith(str(ending).lower()) for ending in accepted_mail_endings)


def get_max_users_per_mail(email: str, cfg: dict) -> int:
    """
    Standard: cfg['max_users_per_mail'] (Fallback 3)
    Override: cfg['email_user_limits'][email] (case-insensitive)
    """
    default_max = int(cfg.get("max_users_per_mail", 3))
    email_lc = normalize_email(email)

    limits = get_email_user_limits_map(cfg)
    if email_lc in limits:
        return limits[email_lc]

    return default_max

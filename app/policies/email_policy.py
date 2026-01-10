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
    Backend-Policy (strikt):
    Erlaubt sind NUR E-Mail-Adressen der Domain @sluz.ch.

    Wichtig:
    - Akzeptiert NICHT @4sluz.ch, @foo.sluz.ch, @sluz.ch.evil.com etc.
    - Ignore cfg.accepted_mail_endings und email_user_limits bewusst,
      damit serverseitig wirklich nur @sluz.ch möglich ist.
    """
    email_lc = normalize_email(email)

    # genau ein "@", lokaler Teil muss existieren, Domain muss exakt "sluz.ch" sein
    if "@" not in email_lc:
        return False

    local, domain = email_lc.rsplit("@", 1)
    local = (local or "").strip()
    domain = (domain or "").strip().lower()

    return bool(local) and domain == "sluz.ch"


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

#!/usr/bin/env python3
# scripts/compare_usernames.py

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, Set, List

import mysql.connector


def _find_default_config_path() -> Path:
    """
    Sucht eine config.json an typischen Orten relativ zum Repo:
    - <repo>/config.json
    - <repo>/app/config.json
    - <repo>/config/config.json
    """
    here = Path(__file__).resolve()
    repo_root = here.parents[1]  # scripts/.. -> repo root

    candidates = [
        repo_root / "config.json",
        repo_root / "app" / "config.json",
        repo_root / "config" / "config.json",
    ]

    for p in candidates:
        if p.is_file():
            return p

    raise FileNotFoundError(
        "Keine config.json gefunden. "
        "Bitte mit --config Pfad/zu/config.json angeben."
    )


def _load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _get_db_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Erwartet Keys:
      db_host, db_port, db_user, db_password, db_database
    Fallback: auch unter cfg["mysql"] oder cfg["db"] versuchen (falls ihr es mal verschoben habt).
    """
    # Direkt (wie im Flask-Code)
    if all(k in cfg for k in ("db_host", "db_port", "db_user", "db_password", "db_database")):
        return {
            "host": cfg["db_host"],
            "port": int(cfg["db_port"]),
            "user": cfg["db_user"],
            "password": cfg["db_password"],
            "database": cfg["db_database"],
        }

    # Fallback: evtl. verschachtelt
    for key in ("mysql", "db", "database"):
        sub = cfg.get(key)
        if isinstance(sub, dict) and all(k in sub for k in ("host", "port", "user", "password", "database")):
            return {
                "host": sub["host"],
                "port": int(sub["port"]),
                "user": sub["user"],
                "password": sub["password"],
                "database": sub["database"],
            }

    missing = ["db_host", "db_port", "db_user", "db_password", "db_database"]
    raise KeyError(
        "config.json enthält nicht die erwarteten DB-Keys. "
        f"Erwartet: {', '.join(missing)} (oder verschachtelt unter mysql/db mit host/port/user/password/database)."
    )


def _norm_username(value: Any) -> str:
    return str(value).strip().lower()


def _fetch_usernames(conn, query: str) -> Set[str]:
    with conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()
    return {_norm_username(r[0]) for r in rows if r and r[0] and str(r[0]).strip()}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Vergleicht Usernames zwischen mysql_whitelist (user) und registrations (minecraft_username)."
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Pfad zur config.json (wenn nicht angegeben, wird in typischen Pfaden gesucht).",
    )
    parser.add_argument(
        "--include-unconfirmed",
        action="store_true",
        help="Wenn gesetzt: vergleicht alle registrations (auch confirmed=0). Standard: nur confirmed=1.",
    )
    parser.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Wenn gesetzt: vergleicht case-sensitiv (Standard: case-insensitive).",
    )

    args = parser.parse_args()

    config_path = Path(args.config).resolve() if args.config else _find_default_config_path()
    cfg = _load_config(config_path)
    db_cfg = _get_db_cfg(cfg)

    # Optional: Env overrides (praktisch für Docker/CI)
    db_cfg["host"] = os.getenv("DB_HOST", db_cfg["host"])
    db_cfg["port"] = int(os.getenv("DB_PORT", str(db_cfg["port"])))
    db_cfg["user"] = os.getenv("DB_USER", db_cfg["user"])
    db_cfg["password"] = os.getenv("DB_PASSWORD", db_cfg["password"])
    db_cfg["database"] = os.getenv("DB_DATABASE", db_cfg["database"])

    def normalize(s: str) -> str:
        return s if args.case_sensitive else s.lower()

    conn = mysql.connector.connect(
        host=db_cfg["host"],
        port=db_cfg["port"],
        user=db_cfg["user"],
        password=db_cfg["password"],
        database=db_cfg["database"],
    )

    try:
        whitelist_query = "SELECT user FROM mysql_whitelist"
        registrations_query = (
            "SELECT minecraft_username FROM registrations"
            if args.include_unconfirmed
            else "SELECT minecraft_username FROM registrations WHERE confirmed = 1"
        )

        whitelist_users = _fetch_usernames(conn, whitelist_query)
        registrations_users = _fetch_usernames(conn, registrations_query)

        # falls case-sensitive: nochmals neu normalisieren (fetch ist aktuell lower())
        if args.case_sensitive:
            # Case-sensitive nur sinnvoll, wenn wir Originalwerte holen.
            # Daher: erneut fetchen ohne lower. (einfach, klar)
            def fetch_raw(q: str) -> Set[str]:
                with conn.cursor() as cur:
                    cur.execute(q)
                    rows = cur.fetchall()
                return {str(r[0]).strip() for r in rows if r and r[0] and str(r[0]).strip()}

            whitelist_users = {normalize(x) for x in fetch_raw(whitelist_query)}
            registrations_users = {normalize(x) for x in fetch_raw(registrations_query)}
        else:
            whitelist_users = {normalize(x) for x in whitelist_users}
            registrations_users = {normalize(x) for x in registrations_users}

        only_in_whitelist: List[str] = sorted(whitelist_users - registrations_users)
        only_in_registrations: List[str] = sorted(registrations_users - whitelist_users)

        mode_label = "case-sensitiv" if args.case_sensitive else "case-insensitive"
        reg_label = "inkl. unconfirmed" if args.include_unconfirmed else "nur confirmed=1"

        print("=== Vergleich Usernames ===")
        print(f"Config: {config_path}")
        print(f"DB: {db_cfg['host']}:{db_cfg['port']} / {db_cfg['database']}")
        print(f"Modus: {mode_label}")
        print(f"Registrations: {reg_label}")
        print()
        print(f"mysql_whitelist: {len(whitelist_users)}")
        print(f"registrations:  {len(registrations_users)}")
        print()

        if not only_in_whitelist and not only_in_registrations:
            print("✅ Alles ok: Jeder Username ist in beiden Tabellen vorhanden.")
            return

        if only_in_whitelist:
            print("❗ In mysql_whitelist, aber NICHT in registrations:")
            for u in only_in_whitelist:
                print(f"  - {u}")
            print()

        if only_in_registrations:
            print("❗ In registrations, aber NICHT in mysql_whitelist:")
            for u in only_in_registrations:
                print(f"  - {u}")
            print()

    finally:
        conn.close()


if __name__ == "__main__":
    main()

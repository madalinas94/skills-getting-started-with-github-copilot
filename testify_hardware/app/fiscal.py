"""Regulile fiscale din România, cu actualizare automată.

Cotele de taxe nu sunt scrise în cod: vin dintr-un fișier de reguli (app/fiscal/ro.json),
în care fiecare set de cote are data de la care se aplică. Aplicația descarcă periodic
versiunea publicată a acestui fișier; când apar reguli noi, le salvează, iar asistentul
îi explică proprietarului ce s-a schimbat. Lunile trecute rămân calculate cu cotele de atunci.
"""

import json
import os
import sqlite3
import urllib.request
from datetime import date, datetime
from pathlib import Path

from .db import get_settings, set_setting

BUNDLED_RULES = Path(__file__).resolve().parent / "fiscal" / "ro.json"
DEFAULT_FEED_URL = (
    "https://raw.githubusercontent.com/madalinas94/skills-getting-started-with-github-copilot/"
    "main/testify_hardware/app/fiscal/ro.json"
)
CHECK_INTERVAL_HOURS = 6
RATE_KEYS = [
    "cas_rate", "cass_rate", "income_tax_rate", "cam_rate",
    "profit_tax_rate", "micro_tax_rate", "dividend_tax_rate",
]
RATE_LABELS = {
    "cas_rate": "CAS (pensie)",
    "cass_rate": "CASS (sănătate)",
    "income_tax_rate": "Impozit pe venit",
    "cam_rate": "CAM",
    "profit_tax_rate": "Impozit pe profit",
    "micro_tax_rate": "Impozit microîntreprindere",
    "dividend_tax_rate": "Impozit pe dividende",
}


def feed_url() -> str:
    return os.environ.get("TESTIFY_FISCAL_FEED", DEFAULT_FEED_URL)


def validate_feed(feed: dict) -> list[dict]:
    """Verifică structura fișierului; o regulă greșită nu trebuie să strice calculele."""
    rules = feed.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("Fișierul nu conține reguli.")
    clean = []
    for rule in rules:
        effective = rule.get("effective_from", "")
        date.fromisoformat(effective)
        rates = rule.get("rates", {})
        values = {}
        for key in RATE_KEYS:
            value = float(rates[key])
            if not 0 <= value <= 100:
                raise ValueError(f"Cota {key} este în afara intervalului 0–100.")
            values[key] = value
        changes = [str(change) for change in rule.get("changes", [])]
        clean.append({"effective_from": effective, "title": str(rule.get("title", "")),
                      "rates": values, "changes": changes})
    return clean


def apply_feed(conn: sqlite3.Connection, feed: dict, mark_seen: bool = False) -> list[str]:
    """Salvează regulile noi sau modificate. Întoarce datele regulilor care s-au schimbat."""
    changed = []
    source = str(feed.get("source", ""))
    for rule in validate_feed(feed):
        rates_json = json.dumps(rule["rates"], sort_keys=True)
        changes_json = json.dumps(rule["changes"], ensure_ascii=False)
        existing = conn.execute(
            "SELECT rates, changes FROM fiscal_rules WHERE effective_from = ?",
            (rule["effective_from"],),
        ).fetchone()
        if existing and existing["rates"] == rates_json and existing["changes"] == changes_json:
            continue
        conn.execute(
            "INSERT INTO fiscal_rules(effective_from, title, rates, changes, source, seen) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(effective_from) DO UPDATE SET "
            "title = excluded.title, rates = excluded.rates, changes = excluded.changes, "
            "source = excluded.source, seen = excluded.seen, received_at = datetime('now')",
            (rule["effective_from"], rule["title"], rates_json, changes_json, source,
             1 if mark_seen else 0),
        )
        changed.append(rule["effective_from"])
    if feed.get("version"):
        set_setting(conn, "fiscal_version", str(feed["version"]))
    return changed


def install_bundled_rules(conn: sqlite3.Connection) -> None:
    """La prima pornire încarcă regulile livrate cu aplicația."""
    if conn.execute("SELECT COUNT(*) FROM fiscal_rules").fetchone()[0] == 0:
        apply_feed(conn, json.loads(BUNDLED_RULES.read_text(encoding="utf-8")), mark_seen=True)


def fetch_feed(url: str, timeout: float = 8) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "TestifyHardware/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def check_for_updates(conn: sqlite3.Connection, url: str | None = None) -> dict:
    """Descarcă fișierul publicat și aplică modificările. Nu aruncă erori: le raportează."""
    url = feed_url() if url is None else url
    now = datetime.now().isoformat(timespec="seconds")
    if not url:
        return {"ok": False, "changed": [], "message": "Actualizarea automată este dezactivată."}
    try:
        changed = apply_feed(conn, fetch_feed(url))
        set_setting(conn, "fiscal_last_check", now)
        set_setting(conn, "fiscal_last_status", "ok")
        message = (f"Am găsit {len(changed)} actualizări." if changed
                   else "Regulile fiscale sunt la zi.")
        return {"ok": True, "changed": changed, "message": message}
    except Exception as error:  # rețea indisponibilă, fișier invalid etc.
        set_setting(conn, "fiscal_last_check", now)
        set_setting(conn, "fiscal_last_status", "error")
        return {"ok": False, "changed": [],
                "message": f"Nu am putut verifica actualizările ({type(error).__name__}). "
                           "Folosesc ultimele reguli salvate."}


def row_to_rule(row: sqlite3.Row) -> dict:
    return {
        "effective_from": row["effective_from"],
        "title": row["title"],
        "rates": json.loads(row["rates"]),
        "changes": json.loads(row["changes"]),
        "source": row["source"],
        "seen": bool(row["seen"]),
        "received_at": row["received_at"],
    }


def rule_for_date(conn: sqlite3.Connection, day: str) -> dict:
    row = conn.execute(
        "SELECT * FROM fiscal_rules WHERE effective_from <= ? ORDER BY effective_from DESC LIMIT 1",
        (day,),
    ).fetchone() or conn.execute(
        "SELECT * FROM fiscal_rules ORDER BY effective_from LIMIT 1"
    ).fetchone()
    if row is None:
        install_bundled_rules(conn)
        return rule_for_date(conn, day)
    return row_to_rule(row)


def settings_for_month(conn: sqlite3.Connection, ym: str) -> dict:
    """Setările firmei plus cotele fiscale valabile la sfârșitul lunii date."""
    from .calc import month_bounds  # import local, calc depinde de acest modul

    rule = rule_for_date(conn, month_bounds(ym)[1])
    return {**get_settings(conn), **rule["rates"], "fiscal_rule": rule["effective_from"]}


def overview(conn: sqlite3.Connection) -> dict:
    settings = get_settings(conn)
    today = date.today().isoformat()
    rules = [row_to_rule(row) for row in conn.execute(
        "SELECT * FROM fiscal_rules ORDER BY effective_from DESC")]
    current = rule_for_date(conn, today)
    return {
        "current": current,
        "upcoming": [rule for rule in rules if rule["effective_from"] > today],
        "history": rules,
        "unseen": [rule for rule in rules if not rule["seen"]],
        "labels": RATE_LABELS,
        "feed_url": feed_url(),
        "version": settings.get("fiscal_version"),
        "last_check": settings.get("fiscal_last_check"),
        "last_status": settings.get("fiscal_last_status"),
    }


def mark_seen(conn: sqlite3.Connection) -> None:
    conn.execute("UPDATE fiscal_rules SET seen = 1 WHERE seen = 0")

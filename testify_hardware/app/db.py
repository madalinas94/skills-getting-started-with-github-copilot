"""Baza de date SQLite: conexiune, schemă și setări implicite."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "testify.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS categories (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT NOT NULL UNIQUE,
    color TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS employees (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT NOT NULL,
    role      TEXT NOT NULL DEFAULT '',
    hire_date TEXT NOT NULL,
    end_date  TEXT,
    notes     TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS salary_history (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id    INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    gross          REAL NOT NULL,
    effective_from TEXT NOT NULL,
    note           TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS sales (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    description TEXT NOT NULL,
    product     TEXT,
    quantity    INTEGER,
    amount      REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS expenses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    category    TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    amount      REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date);
CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date);
"""

# Cotele sunt în procente și pot fi modificate din pagina Setări.
DEFAULT_SETTINGS = {
    "company_name": "Testify Hardware",
    "micro_tax_rate": "1",       # impozit microîntreprindere (% din venituri)
    "cas_rate": "25",            # pensie, reținută din brut
    "cass_rate": "10",           # sănătate, reținută din brut
    "income_tax_rate": "10",     # impozit pe venit salarii
    "cam_rate": "2.25",          # contribuția asiguratorie pentru muncă, plătită de firmă
    "dividend_tax_rate": "16",   # impozit pe dividende, pentru „cât îmi rămâne mie”
}

DEFAULT_CATEGORIES = [
    ("Marfă / furnizori", "#38bdf8"),
    ("Chirie", "#a78bfa"),
    ("Utilități", "#34d399"),
    ("Internet și telefonie", "#2dd4bf"),
    ("Transport", "#fbbf24"),
    ("Combustibil și auto", "#facc15"),
    ("Contabilitate", "#f472b6"),
    ("Marketing", "#fb923c"),
    ("Software și abonamente", "#818cf8"),
    ("Echipamente IT și mobilier", "#60a5fa"),
    ("Comisioane bancare și POS", "#c084fc"),
    ("Asigurări", "#4ade80"),
    ("Mentenanță și reparații", "#f97316"),
    ("Ambalaje și consumabile", "#e879f9"),
    ("Taxe locale și autorizații", "#fda4af"),
    ("Medicina muncii și SSM", "#5eead4"),
    ("Training și cursuri", "#93c5fd"),
    ("Protocol și deplasări", "#fcd34d"),
    ("Altele", "#94a3b8"),
]
# Crește când se adaugă categorii implicite noi, ca să ajungă și în bazele existente.
CATEGORIES_VERSION = "2"


def db_path() -> Path:
    return Path(os.environ.get("TESTIFY_DB", DEFAULT_DB_PATH))


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_conn():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (key, value)
            )
        if get_settings(conn).get("categories_version") != CATEGORIES_VERSION:
            conn.executemany(
                "INSERT OR IGNORE INTO categories(name, color) VALUES (?, ?)", DEFAULT_CATEGORIES
            )
            set_setting(conn, "categories_version", CATEGORIES_VERSION)


def get_settings(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {row["key"]: row["value"] for row in rows}


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )

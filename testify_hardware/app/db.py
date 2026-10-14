"""Baza de date SQLite: conexiune, schemă, migrări și setări implicite."""

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
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL UNIQUE,
    color    TEXT NOT NULL,
    vat_kind TEXT NOT NULL DEFAULT 'standard'
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

CREATE TABLE IF NOT EXISTS products (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    code          TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    category      TEXT NOT NULL DEFAULT '',
    supplier      TEXT NOT NULL DEFAULT '',
    sale_price    REAL NOT NULL DEFAULT 0,
    cost          REAL NOT NULL DEFAULT 0,
    min_stock     INTEGER NOT NULL DEFAULT 0,
    opening_stock INTEGER NOT NULL DEFAULT 0,
    opening_date  TEXT,
    active        INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS clients (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE,
    type          TEXT NOT NULL DEFAULT 'B2C',
    city          TEXT NOT NULL DEFAULT '',
    agent         TEXT NOT NULL DEFAULT '',
    payment_terms INTEGER NOT NULL DEFAULT 0
);

-- Recepții de marfă (NIR): cresc stocul; costul intră în profit abia când marfa se vinde.
CREATE TABLE IF NOT EXISTS purchases (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    date       TEXT NOT NULL,
    doc_number TEXT NOT NULL DEFAULT '',
    supplier   TEXT NOT NULL DEFAULT '',
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    quantity   INTEGER NOT NULL,
    unit_cost  REAL NOT NULL
);

-- O vânzare e fie o factură pe un produs (product_id, quantity, unit_price, unit_cost),
-- fie un total pe zi/lună (fără produs; unit_cost ține atunci costul total al mărfii).
CREATE TABLE IF NOT EXISTS sales (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    date           TEXT NOT NULL,
    description    TEXT NOT NULL,
    product        TEXT,
    quantity       INTEGER,
    amount         REAL NOT NULL,
    invoice_number TEXT,
    product_id     INTEGER REFERENCES products(id) ON DELETE SET NULL,
    client_id      INTEGER REFERENCES clients(id) ON DELETE SET NULL,
    unit_price     REAL,
    unit_cost      REAL,
    due_date       TEXT,
    paid           INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS expenses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    category    TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    amount      REAL NOT NULL,
    supplier    TEXT NOT NULL DEFAULT '',
    vat_kind    TEXT NOT NULL DEFAULT 'standard'
);

CREATE TABLE IF NOT EXISTS fiscal_rules (
    effective_from TEXT PRIMARY KEY,
    title          TEXT NOT NULL DEFAULT '',
    rates          TEXT NOT NULL,
    changes        TEXT NOT NULL DEFAULT '[]',
    source         TEXT NOT NULL DEFAULT '',
    seen           INTEGER NOT NULL DEFAULT 0,
    received_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

INDEXES = """
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date);
CREATE INDEX IF NOT EXISTS idx_sales_product ON sales(product_id);
CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date);
CREATE INDEX IF NOT EXISTS idx_purchases_date ON purchases(date);
CREATE INDEX IF NOT EXISTS idx_purchases_product ON purchases(product_id);
"""

# Coloane adăugate după prima versiune: bazele de date existente le primesc la pornire.
MIGRATIONS = [
    ("categories", "vat_kind", "TEXT NOT NULL DEFAULT 'standard'"),
    ("sales", "invoice_number", "TEXT"),
    ("sales", "product_id", "INTEGER REFERENCES products(id) ON DELETE SET NULL"),
    ("sales", "client_id", "INTEGER REFERENCES clients(id) ON DELETE SET NULL"),
    ("sales", "unit_price", "REAL"),
    ("sales", "unit_cost", "REAL"),
    ("sales", "due_date", "TEXT"),
    ("sales", "paid", "INTEGER NOT NULL DEFAULT 1"),
    ("expenses", "supplier", "TEXT NOT NULL DEFAULT ''"),
    ("expenses", "vat_kind", "TEXT NOT NULL DEFAULT 'standard'"),
]

# Setările firmei. Cotele de taxe nu stau aici, ci în regulile fiscale (vezi fiscal.py).
DEFAULT_SETTINGS = {
    "company_name": "Testify Hardware",
    "owner_name": "Robert",
    "tax_regime": "profit",      # "profit" (impozit pe profit) sau "micro" (microîntreprindere)
    "vat_payer": "1",            # plătitor de TVA, conform raportului contabil
}

# Categoria de TVA implicită: standard (21%), redusă (11%) sau fără TVA (scutit).
DEFAULT_CATEGORIES = [
    ("Marfă / furnizori", "#38bdf8", "standard"),
    ("Chirie", "#a78bfa", "standard"),
    ("Utilități", "#34d399", "standard"),
    ("Internet și telefonie", "#2dd4bf", "standard"),
    ("Transport", "#fbbf24", "standard"),
    ("Combustibil și auto", "#facc15", "standard"),
    ("Contabilitate", "#f472b6", "standard"),
    ("Marketing", "#fb923c", "standard"),
    ("Software și abonamente", "#818cf8", "standard"),
    ("Echipamente IT și mobilier", "#60a5fa", "standard"),
    ("Comisioane bancare și POS", "#c084fc", "none"),
    ("Asigurări", "#4ade80", "none"),
    ("Mentenanță și reparații", "#f97316", "standard"),
    ("Ambalaje și consumabile", "#e879f9", "standard"),
    ("Taxe locale și autorizații", "#fda4af", "none"),
    ("Medicina muncii și SSM", "#5eead4", "none"),
    ("Training și cursuri", "#93c5fd", "standard"),
    ("Protocol și deplasări", "#fcd34d", "standard"),
    ("Altele", "#94a3b8", "standard"),
]
# Crește când se adaugă categorii implicite noi, ca să ajungă și în bazele existente.
CATEGORIES_VERSION = "3"


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


def migrate(conn: sqlite3.Connection) -> None:
    for table, column, ddl in MIGRATIONS:
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        migrate(conn)
        conn.executescript(INDEXES)
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (key, value)
            )
        if get_settings(conn).get("categories_version") != CATEGORIES_VERSION:
            for name, color, vat_kind in DEFAULT_CATEGORIES:
                conn.execute(
                    "INSERT INTO categories(name, color, vat_kind) VALUES (?, ?, ?) "
                    "ON CONFLICT(name) DO UPDATE SET vat_kind = excluded.vat_kind",
                    (name, color, vat_kind),
                )
            set_setting(conn, "categories_version", CATEGORIES_VERSION)

        from .fiscal import install_bundled_rules
        install_bundled_rules(conn)


def get_settings(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {row["key"]: row["value"] for row in rows}


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )

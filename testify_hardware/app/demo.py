"""Datele de pornire: fișierele primite de la firmă (raportul contabil T3 2026 și lista de produse)."""

import sqlite3
from pathlib import Path

from .importer import import_files

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"
SAMPLE_FILES = ["raport_contabil_T3_2026.xlsx", "produse.csv"]


def load_demo_data(conn: sqlite3.Connection) -> dict:
    """Înlocuiește datele existente cu datele firmei din trimestrul III 2026."""
    files = [(name, (SAMPLE_DIR / name).read_bytes()) for name in SAMPLE_FILES]
    return import_files(conn, files, replace=True)

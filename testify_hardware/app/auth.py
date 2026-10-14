"""Autentificare pentru un singur utilizator: parola proprietarului și sesiuni."""

import hashlib
import hmac
import secrets
import sqlite3

from fastapi import Cookie, HTTPException

from .db import get_conn, get_settings, set_setting

COOKIE_NAME = "testify_session"
ITERATIONS = 240_000


def hash_password(password: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS)
    return digest.hex()


def is_setup_done(conn: sqlite3.Connection) -> bool:
    return "password_hash" in get_settings(conn)


def set_password(conn: sqlite3.Connection, password: str) -> None:
    salt = secrets.token_hex(16)
    set_setting(conn, "password_salt", salt)
    set_setting(conn, "password_hash", hash_password(password, salt))


def check_password(conn: sqlite3.Connection, password: str) -> bool:
    settings = get_settings(conn)
    if "password_hash" not in settings:
        return False
    expected = settings["password_hash"]
    return hmac.compare_digest(hash_password(password, settings["password_salt"]), expected)


def create_session(conn: sqlite3.Connection) -> str:
    token = secrets.token_urlsafe(32)
    conn.execute("INSERT INTO sessions(token) VALUES (?)", (token,))
    return token


def is_valid_session(conn: sqlite3.Connection, token: str | None) -> bool:
    if not token:
        return False
    return conn.execute("SELECT 1 FROM sessions WHERE token = ?", (token,)).fetchone() is not None


def require_login(testify_session: str | None = Cookie(default=None)) -> None:
    """Dependență FastAPI: oprește orice cerere fără sesiune validă."""
    with get_conn() as conn:
        if not is_valid_session(conn, testify_session):
            raise HTTPException(status_code=401, detail="Trebuie să vă autentificați.")

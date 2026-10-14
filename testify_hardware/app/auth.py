"""Autentificare pentru un singur utilizator: parola proprietarului și sesiuni."""

import hashlib
import hmac
import secrets
import sqlite3
import time

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


class AttemptLimiter:
    """După 5 încercări greșite la rând, parola și codul de recuperare se blochează 5 minute."""

    def __init__(self, max_failures: int = 5, lock_seconds: int = 300):
        self.max_failures, self.lock_seconds = max_failures, lock_seconds
        self.failures, self.locked_until = 0, 0.0

    def check(self) -> None:
        remaining = self.locked_until - time.monotonic()
        if remaining > 0:
            raise HTTPException(status_code=429, detail=f"Prea multe încercări greșite. "
                                f"Încercați din nou peste {int(remaining // 60) + 1} minute.")

    def failed(self) -> None:
        self.failures += 1
        if self.failures >= self.max_failures:
            self.locked_until = time.monotonic() + self.lock_seconds
            self.failures = 0

    def reset(self) -> None:
        self.failures, self.locked_until = 0, 0.0


limiter = AttemptLimiter()

# Fără caractere ușor de confundat pe hârtie (0/O, 1/I/L).
RECOVERY_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def normalize_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def set_recovery_code(conn: sqlite3.Connection) -> str:
    """Generează un cod de recuperare nou (16 caractere) și salvează doar amprenta lui."""
    raw = "".join(secrets.choice(RECOVERY_ALPHABET) for _ in range(16))
    salt = secrets.token_hex(16)
    set_setting(conn, "recovery_salt", salt)
    set_setting(conn, "recovery_hash", hash_password(raw, salt))
    return "-".join(raw[i:i + 4] for i in range(0, 16, 4))


def has_recovery_code(conn: sqlite3.Connection) -> bool:
    return "recovery_hash" in get_settings(conn)


def check_recovery_code(conn: sqlite3.Connection, code: str) -> bool:
    settings = get_settings(conn)
    if "recovery_hash" not in settings:
        return False
    actual = hash_password(normalize_code(code), settings["recovery_salt"])
    return hmac.compare_digest(actual, settings["recovery_hash"])


def end_all_sessions(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM sessions")


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

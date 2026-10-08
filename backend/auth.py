"""Password hashing and user auth for Campus Customs.

Passwords are never stored in the clear. We store PBKDF2-HMAC-SHA256 digests
in the form:

    pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>

The iteration count is embedded so hashes stay verifiable even if we raise the
work factor later. A legacy 3-part form (pbkdf2_sha256$<salt>$<hash_hex>, used
by some seed rows) is also accepted on verify, using LEGACY_ITERATIONS.

Login sessions: after a successful log in / sign up the server issues a random session token in an
HttpOnly cookie. Only the token's SHA-256 is stored (sessions table), so a leaked DB can't be replayed as
a login. The chat route uses the session to know which customer is talking, so chat history can't be read
or written for another user by sending a different user id.
"""

import hashlib
import hmac
import os
import secrets
import sqlite3

ALGORITHM = "pbkdf2_sha256"
DEFAULT_ITERATIONS = 600_000
# Iteration count used by the legacy 3-part seed hashes, which don't embed one.
LEGACY_ITERATIONS = 120_000
SALT_BYTES = 16


def hash_password(password: str, *, iterations: int = DEFAULT_ITERATIONS) -> str:
    salt = os.urandom(SALT_BYTES).hex()
    digest = _pbkdf2(password, salt, iterations)
    return f"{ALGORITHM}${iterations}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time check of a password against a stored hash string."""
    try:
        parts = stored.split("$")
        if len(parts) == 4:
            algorithm, iterations_s, salt, expected = parts
            iterations = int(iterations_s)
        elif len(parts) == 3:
            # Legacy seed form without an embedded iteration count.
            algorithm, salt, expected = parts
            iterations = LEGACY_ITERATIONS
        else:
            return False
        if algorithm != ALGORITHM:
            return False
        candidate = _pbkdf2(password, salt, iterations)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate, expected)


def _pbkdf2(password: str, salt: str, iterations: int) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    ).hex()


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

SESSION_COOKIE = "cc_session"
SESSION_DAYS = 14

SESSIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,               -- sha256 of the cookie token; the token itself is never stored
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL
)
"""


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def ensure_sessions_table(conn: sqlite3.Connection) -> None:
    conn.execute(SESSIONS_SCHEMA)
    conn.execute("DELETE FROM sessions WHERE expires_at <= datetime('now')")
    conn.commit()


def create_session(conn: sqlite3.Connection, user_id: int) -> str:
    """Store a new session for user_id and return the raw token for the cookie."""
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, datetime('now', ?))",
        (_token_hash(token), user_id, f"+{SESSION_DAYS} days"),
    )
    conn.commit()
    return token


def user_for_session(conn: sqlite3.Connection, token: str | None) -> sqlite3.Row | None:
    """The users row for a live session token, or None (missing, unknown or expired)."""
    if not token:
        return None
    return conn.execute(
        """SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id
           WHERE s.token_hash = ? AND s.expires_at > datetime('now')""",
        (_token_hash(token),),
    ).fetchone()


def delete_session(conn: sqlite3.Connection, token: str | None) -> None:
    if token:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))
        conn.commit()

"""Local accounts, salted password hashes and revocable server-side sessions."""
import hashlib
import hmac
import re
import secrets
import time
from contextlib import closing

from . import database as db

SESSION_SECONDS = 7 * 24 * 60 * 60
ITERATIONS = 600_000


def init_auth() -> None:
    db.init_db()
    with closing(db.connect()) as conn, conn:
        conn.lock("schema")
        conn.execute("""CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at DOUBLE PRECISION NOT NULL
        )""")


def normalize_email(email: str) -> str:
    email = email.strip().lower()
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise ValueError("Enter a valid email address.")
    return email


def _password_hash(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS).hex()
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest}"


def _verify(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, AttributeError):
        return False


def create_user(email: str, password: str, name: str) -> dict:
    email = normalize_email(email)
    name = " ".join(name.split())
    if not name or len(name) > 100:
        raise ValueError("Enter a name between 1 and 100 characters.")
    if not 8 <= len(password) <= 128:
        raise ValueError("Password must contain 8 to 128 characters.")
    try:
        with closing(db.connect()) as conn, conn:
            cursor = conn.execute("INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?) RETURNING id",
                                  (name, email, _password_hash(password), db._now()))
            user_id = cursor.fetchone()[0]
    except db.IntegrityError:
        raise ValueError("An account with that email already exists.") from None
    return {"id": user_id, "email": email, "name": name}


def user_by_email(email: str) -> dict | None:
    with closing(db.connect()) as conn:
        row = conn.execute("SELECT id, email, name FROM users WHERE email = ? AND password_hash IS NOT NULL",
                           (normalize_email(email),)).fetchone()
    return dict(row) if row else None


def login(email: str, password: str) -> str:
    try:
        email = normalize_email(email)
    except ValueError:
        raise ValueError("Invalid email or password.") from None
    with closing(db.connect()) as conn, conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        # Do password hashing even for unknown accounts.
        encoded = row["password_hash"] if row and row["password_hash"] else _DUMMY_HASH
        if not _verify(password, encoded) or not row or not row["password_hash"]:
            raise ValueError("Invalid email or password.")
        token = secrets.token_urlsafe(32)
        conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (time.time(),))
        conn.execute("INSERT INTO sessions VALUES (?, ?, ?)",
                     (_token_hash(token), row["id"], time.time() + SESSION_SECONDS))
    return token


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def session_user(token: str | None) -> dict | None:
    if not token:
        return None
    with closing(db.connect()) as conn:
        row = conn.execute("""SELECT u.id, u.email, u.name FROM sessions s JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ? AND s.expires_at > ?""", (_token_hash(token), time.time())).fetchone()
    return dict(row) if row else None


def logout(token: str) -> None:
    with closing(db.connect()) as conn, conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))


# Constant dummy hash; random salt is not needed for a value that never authenticates.
_DUMMY_HASH = _password_hash("not-an-account-password", "00" * 16)

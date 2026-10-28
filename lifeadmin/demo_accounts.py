"""Default presentation accounts, including migration of the original demo user."""
import os
from contextlib import closing

from . import auth, database as db

DEMO_ACCOUNTS = (
    ("demostudent@example.com", "demostudent", "Demo Student"),
    ("demofaculty@example.com", "demofaculty", "Demo Faculty"),
)


def seed_demo_accounts() -> None:
    with closing(db.connect()) as conn, conn:
        # The API and Streamlit may start together against a fresh database.
        conn.lock("demo")
        for email, password, name in DEMO_ACCOUNTS:
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if user is None and email == "demostudent@example.com":
                user = conn.execute("SELECT * FROM users WHERE email = 'demo@example.com'").fetchone()
            if user is None:
                conn.execute("INSERT INTO users (email, name, password_hash, created_at) VALUES (?, ?, ?, ?)",
                             (email, name, auth._password_hash(password), db._now()))
            else:
                encoded = user["password_hash"]
                if not encoded or not auth._verify(password, encoded):
                    encoded = auth._password_hash(password)
                conn.execute("UPDATE users SET email = ?, name = ?, password_hash = ? WHERE id = ?",
                             (email, name, encoded, user["id"]))


def seed_if_enabled() -> None:
    if os.environ.get("LIFEADMIN_SEED_DEMO_USERS", "false").lower() == "true":
        seed_demo_accounts()

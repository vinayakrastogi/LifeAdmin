"""User-scoped persistence, locally in SQLite or shared through PostgreSQL."""
from __future__ import annotations

import os
from contextlib import closing
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set

from .models import Document
from .storage import Connection, IntegrityError, Row, database_url

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("LIFEADMIN_DB", BASE_DIR / "data" / "lifeadmin.db"))

DOC_COLUMNS = [
    "filename", "doc_type", "holder_name", "doc_number", "organization",
    "vehicle_no", "amount", "start_date", "expiry_date", "notes",
    "stored_path", "uploaded_at",
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    filename TEXT NOT NULL,
    doc_type TEXT NOT NULL DEFAULT 'Other',
    holder_name TEXT DEFAULT '',
    doc_number TEXT DEFAULT '',
    organization TEXT DEFAULT '',
    vehicle_no TEXT DEFAULT '',
    amount TEXT DEFAULT '',
    start_date TEXT DEFAULT '',
    expiry_date TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    stored_path TEXT DEFAULT '',
    uploaded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    dismissed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS activity_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    action TEXT NOT NULL,
    detail TEXT DEFAULT '',
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def is_postgres() -> bool:
    return database_url(DB_PATH).startswith("postgresql+")


def connect() -> Connection:
    url = database_url(DB_PATH)
    if url.startswith("sqlite:"):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return Connection(url)


_current_user: ContextVar[int | None] = ContextVar("lifeadmin_user", default=None)


def set_current_user(user_id: int | None) -> None:
    _current_user.set(user_id)


def current_user_id() -> int:
    user_id = _current_user.get()
    if user_id is None:
        raise PermissionError("Sign in to access your data.")
    return user_id


def init_db() -> None:
    with closing(connect()) as conn, conn:
        conn.lock("schema")
        conn.executescript(SCHEMA)
        # Old unowned data remains inaccessible until explicitly reset or migrated.
        for table, additions in {
            "users": {"email": "TEXT", "password_hash": "TEXT"},
            "documents": {"user_id": "INTEGER REFERENCES users(id)"},
            "activity_logs": {"user_id": "INTEGER REFERENCES users(id)"},
        }.items():
            columns = conn.columns(table)
            for column, definition in additions.items():
                if column not in columns:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_email ON users(email)")


def get_user_name() -> str:
    with closing(connect()) as conn:
        row = conn.execute("SELECT name FROM users WHERE id = ?", (current_user_id(),)).fetchone()
    return row[0] if row else ""


def set_user_name(name: str) -> None:
    name = name.strip()
    if not name:
        raise ValueError("Name cannot be empty")
    with closing(connect()) as conn, conn:
        conn.execute("UPDATE users SET name = ? WHERE id = ?", (name[:100], current_user_id()))
    log("PROFILE", f"name set to {name}")


def log(action: str, detail: str = "") -> None:
    with closing(connect()) as conn, conn:
        conn.execute(
            "INSERT INTO activity_logs (user_id, action, detail, created_at) VALUES (?, ?, ?, ?)",
            (current_user_id(), action, detail, _now()),
        )


def add_document(doc: Document) -> int:
    doc.uploaded_at = doc.uploaded_at or _now()
    values = doc.to_dict()
    with closing(connect()) as conn, conn:
        cur = conn.execute(
            f"INSERT INTO documents (user_id, {', '.join(DOC_COLUMNS)}) "
            f"VALUES (?, {', '.join('?' for _ in DOC_COLUMNS)}) RETURNING id",
            [current_user_id(), *[values[c] for c in DOC_COLUMNS]],
        )
        doc_id = cur.fetchone()[0]
    log("ADD", f"{doc.filename} ({doc.doc_type})")
    return doc_id


def update_document(doc: Document) -> None:
    if doc.id is None:
        raise ValueError("Cannot update a document without an id")
    values = doc.to_dict()
    sets = ", ".join(f"{c} = ?" for c in DOC_COLUMNS)
    with closing(connect()) as conn, conn:
        changed = conn.execute(f"UPDATE documents SET {sets} WHERE id = ? AND user_id = ?",
                              [values[c] for c in DOC_COLUMNS] + [doc.id, current_user_id()]).rowcount
        if not changed:
            raise PermissionError("Document not found.")
    log("UPDATE", f"{doc.filename} (id {doc.id})")


def delete_document(doc_id: int) -> None:
    doc = get_document(doc_id)
    with closing(connect()) as conn, conn:
        conn.execute("DELETE FROM documents WHERE id = ? AND user_id = ?", (doc_id, current_user_id()))
    if doc:
        if doc.stored_path:
            try:
                Path(doc.stored_path).unlink(missing_ok=True)
            except OSError:
                pass
        log("DELETE", f"{doc.filename} (id {doc_id})")


def get_document(doc_id: int) -> Optional[Document]:
    with closing(connect()) as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ? AND user_id = ?", (doc_id, current_user_id())).fetchone()
    return Document.from_row({k: row[k] for k in row.keys() if k != "user_id"}) if row else None


def list_documents() -> List[Document]:
    with closing(connect()) as conn:
        rows = conn.execute("SELECT * FROM documents WHERE user_id = ? ORDER BY id DESC", (current_user_id(),)).fetchall()
    return [Document.from_row({k: r[k] for k in r.keys() if k != "user_id"}) for r in rows]


def dismiss_reminder(doc_id: int) -> None:
    """Mark a reminder as completed (it moves to the Completed tab)."""
    if get_document(doc_id) is None:
        raise PermissionError("Document not found.")
    with closing(connect()) as conn, conn:
        conn.execute("INSERT INTO reminders (document_id, dismissed_at) VALUES (?, ?)",
                     (doc_id, _now()))
    log("COMPLETE", f"reminder for document id {doc_id}")


def dismissed_ids() -> Set[int]:
    with closing(connect()) as conn:
        rows = conn.execute("""SELECT DISTINCT document_id FROM reminders r
            JOIN documents d ON d.id = r.document_id WHERE d.user_id = ?""", (current_user_id(),)).fetchall()
    return {r[0] for r in rows}


def restore_reminder(doc_id: int) -> None:
    if get_document(doc_id) is None:
        raise PermissionError("Document not found.")
    with closing(connect()) as conn, conn:
        conn.execute("DELETE FROM reminders WHERE document_id = ?", (doc_id,))
    log("RESTORE", f"reminder for document id {doc_id}")


# Friendlier names used by the Reminders page.
complete_reminder = dismiss_reminder
completed_ids = dismissed_ids


def list_logs(limit: int = 50) -> List[Row]:
    with closing(connect()) as conn:
        return conn.execute(
            "SELECT * FROM activity_logs WHERE user_id = ? ORDER BY id DESC LIMIT ?", (current_user_id(), limit)
        ).fetchall()

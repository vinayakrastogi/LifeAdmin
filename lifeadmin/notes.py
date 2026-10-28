"""Notes persisted by LifeAdmin; callers never share its database."""
from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4

from . import database


def init_notes() -> None:
    with closing(database.connect()) as conn, conn:
        conn.lock("schema")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS notes (
                id TEXT PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                source_app TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                request_id TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(source_app, owner_id, request_id)
            );
            CREATE INDEX IF NOT EXISTS notes_scope
                ON notes(source_app, owner_id, resource_id, created_at);
        """)
        columns = conn.columns("notes")
        if "user_id" not in columns:
            conn.execute("ALTER TABLE notes ADD COLUMN user_id INTEGER REFERENCES users(id)")
        conn.execute("CREATE INDEX IF NOT EXISTS notes_user ON notes(user_id, created_at)")


def create_note(*, user_id: int, source_app: str, owner_id: str, resource_id: str,
                request_id: str, title: str, content: str) -> dict:
    """A repeated request returns the original note, avoiding duplicate saves after timeouts."""
    now = datetime.now(timezone.utc).isoformat()
    with closing(database.connect()) as conn, conn:
        conn.execute("""
            INSERT INTO notes (id, user_id, source_app, owner_id, resource_id, request_id, title, content, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_app, owner_id, request_id) DO NOTHING
        """, (str(uuid4()), user_id, source_app, owner_id, resource_id, request_id, title, content, now))
        row = conn.execute("""
            SELECT * FROM notes WHERE source_app = ? AND owner_id = ? AND request_id = ? AND user_id = ?
        """, (source_app, owner_id, request_id, user_id)).fetchone()
        if row is None:
            raise ValueError("This request ID belongs to another account.")
    return dict(row)


def list_notes(user_id: int, source_app: str | None = None, owner_id: str | None = None,
               resource_id: str | None = None, limit: int = 100) -> list[dict]:
    filters, values = ["user_id = ?"], [user_id]
    for column, value in (("source_app", source_app), ("owner_id", owner_id), ("resource_id", resource_id)):
        if value is not None:
            filters.append(f"{column} = ?")
            values.append(value)
    where = " WHERE " + " AND ".join(filters) if filters else ""
    with closing(database.connect()) as conn:
        rows = conn.execute(
            "SELECT * FROM notes" + where + " ORDER BY created_at DESC, id DESC LIMIT ?",
            [*values, limit],
        ).fetchall()
    return [dict(row) for row in rows]


def delete_note(note_id: str, user_id: int, source_app: str | None = None, owner_id: str | None = None) -> bool:
    filters, values = ["id = ?", "user_id = ?"], [note_id, user_id]
    for column, value in (("source_app", source_app), ("owner_id", owner_id)):
        if value is not None:
            filters.append(f"{column} = ?")
            values.append(value)
    with closing(database.connect()) as conn, conn:
        return conn.execute(
            "DELETE FROM notes WHERE " + " AND ".join(filters), values,
        ).rowcount > 0

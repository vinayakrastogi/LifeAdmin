from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import hashlib
import os

import pytest

from lifeadmin import auth, database as db, notes
from lifeadmin.demo import reset_database
from lifeadmin.demo_accounts import seed_demo_accounts
from lifeadmin.models import Document
from lifeadmin.storage import database_url
from scripts.migrate_to_postgres import migrate


def test_invalid_remote_url_never_falls_back_to_sqlite(tmp_path, monkeypatch):
    monkeypatch.setenv("LIFEADMIN_DATABASE_URL", "mysql://wrong/db")
    with pytest.raises(ValueError, match="PostgreSQL"):
        db.connect()
    assert not (tmp_path / "unintended.db").exists()


def test_postgres_alias_and_ssl_options_are_preserved(tmp_path, monkeypatch):
    monkeypatch.setenv("LIFEADMIN_DATABASE_URL", "postgres://u:p@db.invalid/lifeadmin?sslmode=require")
    assert database_url(tmp_path / "x.db") == "postgresql+psycopg2://u:p@db.invalid/lifeadmin?sslmode=require"


@pytest.mark.skipif(not os.environ.get("LIFEADMIN_TEST_DATABASE_URL"), reason="Needs disposable PostgreSQL")
def test_concurrent_startup_and_seeding_are_safe():
    def start(_):
        auth.init_auth()
        notes.init_notes()
        seed_demo_accounts()
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(start, range(3)))
    with closing(db.connect()) as conn:
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 2


@pytest.mark.skipif(not os.environ.get("LIFEADMIN_TEST_DATABASE_URL"), reason="Needs disposable PostgreSQL")
def test_migration_preserves_accounts_notes_sessions_and_ids(tmp_path, monkeypatch):
    destination = os.environ["LIFEADMIN_DATABASE_URL"]
    with closing(db.connect()) as conn, conn:
        conn.execute("DELETE FROM users")
    monkeypatch.delenv("LIFEADMIN_DATABASE_URL")
    source = tmp_path / "source.db"
    monkeypatch.setattr(db, "DB_PATH", source)
    auth.init_auth()
    notes.init_notes()
    student = auth.create_user("learner@example.com", "LearnerPassword!", "Learner")
    other = auth.create_user("other@example.com", "OtherPassword!", "Other")
    db.set_current_user(student["id"])
    document_id = db.add_document(Document("upload.txt"))
    db.complete_reminder(document_id)
    token = auth.login(student["email"], "LearnerPassword!")
    saved = notes.create_note(user_id=student["id"], source_app="pylearn", owner_id="pylearn:1",
                              resource_id="loops", request_id="migration", title="Kept", content="My note")
    fingerprint = hashlib.sha256(source.read_bytes()).digest()
    monkeypatch.setenv("LIFEADMIN_DATABASE_URL", destination)
    counts = migrate(source)
    assert counts["users"] == 2 and counts["notes"] == 1
    assert hashlib.sha256(source.read_bytes()).digest() == fingerprint
    assert auth.session_user(token)["id"] == student["id"]
    assert notes.list_notes(student["id"])[0]["id"] == saved["id"]
    assert notes.list_notes(other["id"]) == []
    assert db.get_document(document_id).filename == "upload.txt"
    assert document_id in db.completed_ids()
    # Sequences are advanced past imported IDs, not left at 1.
    assert auth.create_user("third@example.com", "ThirdPassword!", "Third")["id"] > other["id"]
    assert db.add_document(Document("next.txt")) > document_id
    with pytest.raises(ValueError, match="empty"):
        migrate(source)
    with pytest.raises(ValueError, match="disabled"):
        reset_database()

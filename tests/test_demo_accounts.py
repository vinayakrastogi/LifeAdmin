from contextlib import closing

import pytest

from lifeadmin import auth, database as db, notes
from lifeadmin.demo_accounts import DEMO_ACCOUNTS, seed_demo_accounts, seed_if_enabled


def test_demo_accounts_have_the_requested_logins_and_seeding_is_repeatable():
    seed_demo_accounts()
    with closing(db.connect()) as conn:
        before = [tuple(row) for row in conn.execute("SELECT id, email, password_hash FROM users ORDER BY id")]
    assert len(before) == 2
    for email, password, name in DEMO_ACCOUNTS:
        token = auth.login(email, password)
        assert auth.session_user(token)["name"] == name
        auth.logout(token)
    seed_demo_accounts()
    with closing(db.connect()) as conn:
        assert [tuple(row) for row in conn.execute("SELECT id, email, password_hash FROM users ORDER BY id")] == before


def test_legacy_demo_migration_preserves_note_ownership(tmp_path, monkeypatch):
    monkeypatch.delenv("LIFEADMIN_DATABASE_URL", raising=False)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "legacy.db")
    auth.init_auth()
    notes.init_notes()
    old = auth.create_user("demo@example.com", "PyLearnDemo123!", "Demo Learner")
    note = notes.create_note(user_id=old["id"], source_app="pylearn", owner_id="pylearn:1",
                             resource_id="python/loops", request_id="existing", title="Existing note", content="Keep this.")
    seed_demo_accounts()
    student = auth.user_by_email("demostudent@example.com")
    assert student["id"] == old["id"]
    assert notes.list_notes(student["id"])[0]["id"] == note["id"]
    assert notes.list_notes(auth.user_by_email("demofaculty@example.com")["id"]) == []
    with pytest.raises(ValueError):
        auth.login("demo@example.com", "PyLearnDemo123!")


def test_startup_seeding_can_be_disabled(monkeypatch):
    seed_if_enabled()
    assert auth.user_by_email("demofaculty@example.com") is None
    monkeypatch.setenv("LIFEADMIN_SEED_DEMO_USERS", "true")
    seed_if_enabled()
    assert auth.user_by_email("demofaculty@example.com") is not None

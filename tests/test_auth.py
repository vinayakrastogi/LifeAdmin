from contextlib import closing
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from lifeadmin import auth, database as db, notes
from lifeadmin.api import app
from lifeadmin.models import Document


def test_passwords_and_sessions_are_hashed_and_logout_revokes(local_user):
    with closing(db.connect()) as conn:
        stored = conn.execute("SELECT password_hash FROM users WHERE id = ?", (local_user["id"],)).fetchone()[0]
    assert "demostudent" not in stored
    assert stored.startswith("pbkdf2_sha256$")
    token = auth.login(" DEMOSTUDENT@EXAMPLE.COM ", "demostudent")
    with closing(db.connect()) as conn:
        assert conn.execute("SELECT token_hash FROM sessions").fetchone()[0] != token
    assert auth.session_user(token)["id"] == local_user["id"]
    auth.logout(token)
    assert auth.session_user(token) is None
    for email in ("demostudent@example.com", "missing@example.com"):
        with pytest.raises(ValueError, match="Invalid email or password"):
            auth.login(email, "wrong-password")


def test_expired_sessions_are_rejected():
    token = auth.login("demostudent@example.com", "demostudent")
    with closing(db.connect()) as conn, conn:
        conn.execute("UPDATE sessions SET expires_at = 0")
    assert auth.session_user(token) is None


def test_registration_validation():
    with pytest.raises(ValueError, match="already exists"):
        auth.create_user("DEMOSTUDENT@example.com", "another-password", "Other")
    for email, password, name in (("invalid", "valid-password", "Name"),
                                   ("new@example.com", "short", "Name"),
                                   ("new@example.com", "valid-password", "  ")):
        with pytest.raises(ValueError):
            auth.create_user(email, password, name)


def test_documents_profiles_reminders_and_logs_are_private(local_user):
    doc = Document("private.txt", notes="private document")
    doc.id = db.add_document(doc)
    db.complete_reminder(doc.id)
    other = auth.create_user("other@example.com", "OtherPassword123!", "Other Learner")
    db.set_current_user(other["id"])
    assert db.list_documents() == []
    assert db.get_document(doc.id) is None
    assert db.list_logs() == []
    assert db.completed_ids() == set()
    db.set_user_name("Other Name")
    with pytest.raises(PermissionError):
        db.update_document(doc)
    with pytest.raises(PermissionError):
        db.complete_reminder(doc.id)
    with pytest.raises(PermissionError):
        db.restore_reminder(doc.id)
    db.delete_document(doc.id)
    db.set_current_user(local_user["id"])
    assert db.get_document(doc.id) is not None
    assert db.get_user_name() == "Demo Student"
    db.set_current_user(None)
    with pytest.raises(PermissionError):
        db.list_documents()


def test_http_auth_and_note_ownership(local_user, monkeypatch):
    key = "integration-key-" + "x" * 32
    monkeypatch.setenv("LIFEADMIN_API_KEY", key)
    monkeypatch.setenv("LIFEADMIN_SOURCE_APP", "pylearn")
    with TestClient(app) as client:
        assert client.get("/api/v1/me/notes").status_code == 401
        assert client.post("/api/v1/auth/login", json={"email": "demostudent@example.com", "password": "wrong"}).status_code == 401
        login = client.post("/api/v1/auth/login", json={"email": "demostudent@example.com", "password": "demostudent"})
        assert login.status_code == 200
        demo_header = {"Authorization": "Bearer " + login.json()["access_token"]}
        assert client.get("/api/v1/auth/me", headers=demo_header).json()["email"] == "demostudent@example.com"
        body = dict(owner_id="pylearn:99", owner_email="demostudent@example.com", resource_id="python/loops",
                    request_id=str(uuid4()), title="Loop notes", content="Only the demo learner can see this.")
        saved = client.post("/api/v1/notes", json=body, headers={"X-API-Key": key})
        assert saved.status_code == 201
        note_id = saved.json()["id"]
        assert client.get("/api/v1/me/notes", headers=demo_header).json()[0]["id"] == note_id
        assert client.post("/api/v1/auth/register", json={"email": "other@example.com", "password": "OtherPassword123!", "name": "Other"}).status_code == 201
        other_login = client.post("/api/v1/auth/login", json={"email": "other@example.com", "password": "OtherPassword123!"})
        other_header = {"Authorization": "Bearer " + other_login.json()["access_token"]}
        assert client.get("/api/v1/me/notes", headers=other_header).json() == []
        assert client.get("/api/v1/me/notes?owner_id=pylearn:99&user_id=1", headers=other_header).json() == []
        assert client.delete(f"/api/v1/me/notes/{note_id}", headers=other_header).status_code == 404
        assert client.get("/api/v1/notes", params={"owner_id": "pylearn:99", "owner_email": "other@example.com", "resource_id": "python/loops"}, headers={"X-API-Key": key}).json() == []
        assert client.post("/api/v1/notes", json={**body, "owner_email": "missing@example.com"}, headers={"X-API-Key": key}).status_code == 409
        own = client.post("/api/v1/me/notes", json={"title": "Own note", "content": "My own content", "request_id": str(uuid4())}, headers=other_header)
        assert own.status_code == 201
        assert len(client.get("/api/v1/me/notes", headers=demo_header).json()) == 1
        assert client.delete(f"/api/v1/me/notes/{note_id}", headers=demo_header).status_code == 204
        assert client.post("/api/v1/auth/logout", headers=demo_header).status_code == 204
        assert client.get("/api/v1/me/notes", headers=demo_header).status_code == 401

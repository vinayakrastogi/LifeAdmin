from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from lifeadmin import database
from lifeadmin.api import app

KEY = "test-key-" + "a" * 32


@pytest.fixture
def client(local_user, monkeypatch):
    monkeypatch.setenv("LIFEADMIN_API_KEY", KEY)
    monkeypatch.setenv("LIFEADMIN_SOURCE_APP", "pylearn")
    with TestClient(app) as client:
        client.headers["X-API-Key"] = KEY
        yield client


def payload(**changes):
    return dict(owner_id="pylearn:1", owner_email="demostudent@example.com", resource_id="python/loops", request_id=str(uuid4()),
                title="Loops", content="A for loop iterates over items.", **changes)


def test_notes_require_key_and_missing_configuration_fails_closed(client, monkeypatch):
    assert client.get("/health").json()["status"] == "ok"
    client.headers.pop("X-API-Key")
    params = dict(owner_id="pylearn:1", owner_email="demostudent@example.com", resource_id="python/loops")
    assert client.get("/api/v1/notes", params=params).status_code == 401
    monkeypatch.delenv("LIFEADMIN_API_KEY")
    assert client.get("/api/v1/notes", params=params).status_code == 503


def test_create_list_retry_and_owner_scoping(client):
    body = payload()
    created = client.post("/api/v1/notes", json=body)
    assert created.status_code == 201
    note = created.json()
    assert note["content"] == body["content"]
    assert client.post("/api/v1/notes", json=body).json()["id"] == note["id"]
    params = dict(owner_id=body["owner_id"], owner_email=body["owner_email"], resource_id=body["resource_id"])
    assert len(client.get("/api/v1/notes", params=params).json()) == 1
    assert client.get("/api/v1/notes", params={**params, "owner_id": "pylearn:2"}).json() == []
    assert client.get("/api/v1/notes", params={**params, "resource_id": "python/strings"}).json() == []
    path = f'/api/v1/notes/{note["id"]}'
    assert client.delete(path, params={"owner_id": "pylearn:2", "owner_email": body["owner_email"]}).status_code == 404
    assert client.delete(path, params={"owner_id": body["owner_id"], "owner_email": body["owner_email"]}).status_code == 204
    assert client.get("/api/v1/notes", params=params).json() == []


def test_source_app_is_key_scoped(client, monkeypatch):
    body = payload()
    client.post("/api/v1/notes", json=body)
    monkeypatch.setenv("LIFEADMIN_SOURCE_APP", "other-app")
    params = dict(owner_id=body["owner_id"], owner_email=body["owner_email"], resource_id=body["resource_id"])
    assert client.get("/api/v1/notes", params=params).json() == []


@pytest.mark.parametrize("changes", [{"content": "  "}, {"content": "x" * 20001},
                                      {"owner_id": ""}, {"source_app": "forged"},
                                      {"request_id": "invalid"}])
def test_invalid_notes_are_rejected(client, changes):
    body = {**payload(), **changes}
    assert client.post("/api/v1/notes", json=body).status_code == 422


def test_notes_persist_across_api_restarts(client):
    note = client.post("/api/v1/notes", json=payload()).json()
    with TestClient(app) as restarted:
        response = restarted.get("/api/v1/notes", headers={"X-API-Key": KEY},
                                 params=dict(owner_id="pylearn:1", owner_email="demostudent@example.com", resource_id="python/loops"))
    assert response.json()[0]["id"] == note["id"]

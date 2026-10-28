"""Independent HTTP API. Run with: uvicorn lifeadmin.api:app --host 0.0.0.0 --port 8001 --env-file .env"""
import hmac
import os
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from . import auth, notes
from .demo_accounts import seed_if_enabled

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Scope = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    auth.init_auth()
    seed_if_enabled()
    notes.init_notes()
    yield


app = FastAPI(title="LifeAdmin Notes API", version="1.0.0", lifespan=lifespan)
bearer = HTTPBearer(auto_error=False)


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    user = auth.session_user(credentials.credentials if credentials else None)
    if user is None:
        raise HTTPException(401, "Sign in to LifeAdmin.", headers={"WWW-Authenticate": "Bearer"})
    return user


def require_key(x_api_key: str = Header(default="")) -> str:
    expected = os.environ.get("LIFEADMIN_API_KEY", "")
    if len(expected) < 32:
        raise HTTPException(503, "Configure LIFEADMIN_API_KEY with at least 32 characters.")
    if not hmac.compare_digest(x_api_key.encode(), expected.encode()):
        raise HTTPException(401, "Invalid API key.")
    # The API key represents this application; the browser cannot choose a source app.
    return os.environ.get("LIFEADMIN_SOURCE_APP", "pylearn")


class NoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    owner_id: Scope
    owner_email: Text = Field(max_length=254)
    resource_id: Scope
    request_id: UUID
    title: Text = Field(max_length=200)
    content: Text = Field(max_length=20_000)


class NoteResponse(BaseModel):
    id: UUID
    source_app: str
    owner_id: str
    resource_id: str
    request_id: UUID
    title: str
    content: str
    created_at: str


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class RegisterRequest(LoginRequest):
    name: Text = Field(max_length=100)


class UserResponse(BaseModel):
    id: int
    email: str
    name: str


class SessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class PersonalNoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Text = Field(max_length=200)
    content: Text = Field(max_length=20_000)
    request_id: UUID


def integration_user(owner_email: str) -> dict:
    try:
        user = auth.user_by_email(owner_email)
    except ValueError:
        user = None
    if user is None:
        raise HTTPException(409, "Create a LifeAdmin account using the same email as your PyLearn account, then retry.")
    return user


@app.post("/api/v1/auth/register", response_model=UserResponse, status_code=201)
def register(payload: RegisterRequest):
    try:
        return auth.create_user(payload.email, payload.password, payload.name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


@app.post("/api/v1/auth/login", response_model=SessionResponse)
def login(payload: LoginRequest):
    try:
        token = auth.login(payload.email, payload.password)
    except ValueError:
        raise HTTPException(401, "Invalid email or password.") from None
    return {"access_token": token, "user": auth.session_user(token)}


@app.get("/api/v1/auth/me", response_model=UserResponse)
def me(user: dict = Depends(current_user)):
    return user


@app.post("/api/v1/auth/logout", status_code=204)
def logout(user: dict = Depends(current_user), credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    auth.logout(credentials.credentials)
    return Response(status_code=204)


@app.get("/api/v1/me/notes", response_model=list[NoteResponse])
def personal_notes(user: dict = Depends(current_user), limit: int = Query(default=100, ge=1, le=100)):
    return notes.list_notes(user["id"], limit=limit)


@app.post("/api/v1/me/notes", response_model=NoteResponse, status_code=201)
def create_personal_note(payload: PersonalNoteCreate, user: dict = Depends(current_user)):
    return notes.create_note(user_id=user["id"], source_app="lifeadmin", owner_id=str(user["id"]),
                             resource_id="personal", **payload.model_dump(mode="json"))


@app.delete("/api/v1/me/notes/{note_id}", status_code=204)
def delete_personal_note(note_id: UUID, user: dict = Depends(current_user)):
    if not notes.delete_note(str(note_id), user["id"]):
        raise HTTPException(404, "Note not found.")
    return Response(status_code=204)


@app.get("/health")
def health():
    return {"status": "ok", "service": "lifeadmin"}


@app.post("/api/v1/notes", response_model=NoteResponse, status_code=201)
def create_note(payload: NoteCreate, source_app: str = Depends(require_key)):
    user = integration_user(payload.owner_email)
    data = payload.model_dump(mode="json")
    data.pop("owner_email")
    try:
        return notes.create_note(user_id=user["id"], source_app=source_app, **data)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None


@app.get("/api/v1/notes", response_model=list[NoteResponse])
def list_notes(owner_id: Scope, owner_email: Scope, resource_id: Scope,
               limit: int = Query(default=100, ge=1, le=100),
               source_app: str = Depends(require_key)):
    user = integration_user(owner_email)
    return notes.list_notes(user["id"], source_app, owner_id, resource_id, limit)


@app.delete("/api/v1/notes/{note_id}", status_code=204)
def delete_note(note_id: UUID, owner_id: Scope, owner_email: Scope, source_app: str = Depends(require_key)):
    user = integration_user(owner_email)
    if not notes.delete_note(str(note_id), user["id"], source_app, owner_id):
        raise HTTPException(404, "Note not found.")
    return Response(status_code=204)

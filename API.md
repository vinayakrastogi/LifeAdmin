# LifeAdmin login and private notes API

LifeAdmin runs independently of PyLearn and is not Dockerized. The API and
Streamlit interface share only LifeAdmin's own local SQLite database.

## Run locally

For the configured fixed HTTPS endpoint and one-command API/tunnel launcher,
see [NGROK_SETUP.md](NGROK_SETUP.md). Run `python scripts/run_api.py` after adding
the ngrok authtoken to the ignored local `.env` file.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Fresh checkout only: copy .env.example to .env and set LIFEADMIN_API_KEY.
uvicorn lifeadmin.api:app --env-file .env --host 0.0.0.0 --port 8001
```

In a second activated terminal, run:

```bash
streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

UI: `http://localhost:8501`. API docs: `http://localhost:8001/docs`.
Health: `http://localhost:8001/health`.

The presentation accounts are:

| Account | Email | Password |
|---|---|---|
| Student | `demostudent@example.com` | `demostudent` |
| Faculty | `demofaculty@example.com` | `demofaculty` |

With `LIFEADMIN_SEED_DEMO_USERS=true`, startup creates or updates these accounts.
Both are ordinary, separate LifeAdmin users; the faculty role applies in edT.
Other users can register in the UI. Login is required before any user data is
shown. Notes, documents, reminders and activity history are scoped to the signed-in
user. The profile changes only that user's name. Logout clears the Streamlit
session and revokes its server token. Passwords use salted PBKDF2 hashes;
revocable session tokens are stored hashed and expire after seven days.

To explicitly reset later, stop both servers and run:

```bash
python scripts/reset_database.py --confirm
```

This backs up the current SQLite database and creates only the two demo accounts.
It does not load sample documents or notes. It is not needed for normal startup.
Existing legacy data without an owner is not displayed to newly registered users.
Default path: `data/lifeadmin.db`, relative to the project root. `LIFEADMIN_DB`
can override this; keep both processes pointed at the same database. The API
loads `.env` via Uvicorn; the Streamlit app loads this project's `.env` too.

## User authentication API

| Method | Route | Body / result |
|---|---|---|
| POST | `/api/v1/auth/register` | `{email, password, name}`; returns public account fields |
| POST | `/api/v1/auth/login` | `{email, password}`; returns `access_token`, `token_type`, `user` |
| GET | `/api/v1/auth/me` | Returns the current account |
| POST | `/api/v1/auth/logout` | Revokes the current token; returns 204 |

Use `Authorization: Bearer <access_token>` after login. Registration requires
an email, a name (1-100 characters) and a password (8-128 characters). Wrong
credentials return 401; duplicate registration returns 400.

| Method | User notes route | Body / result |
|---|---|---|
| GET | `/api/v1/me/notes` | Current user's latest 100 notes, including PyLearn notes |
| POST | `/api/v1/me/notes` | `{title, content, request_id}`; returns saved personal note |
| DELETE | `/api/v1/me/notes/{id}` | Deletes only the current user's note; returns 204 or 404 |

These endpoints derive ownership from the Bearer token. An API key or a user ID
supplied by the client cannot replace that login.

## PyLearn integration API

These routes use `X-API-Key` and are for a trusted application backend. Set
`LIFEADMIN_API_KEY` (at least 32 characters) in `.env`, with the same value in
PyLearn's backend. `LIFEADMIN_SOURCE_APP` defaults to `pylearn`.

Create using `POST /api/v1/notes`:

```json
{
  "owner_id": "pylearn:42",
  "owner_email": "demostudent@example.com",
  "resource_id": "module-1/lesson-1",
  "request_id": "49df5579-40bf-4dbf-9a71-9df5f4d5cb1f",
  "title": "Python variables",
  "content": "Variables hold references to Python objects."
}
```

The email must already be registered in LifeAdmin. Otherwise the API returns 409
with registration guidance. PyLearn supplies the email from its logged-in user;
there is no password sharing or direct database access between the projects.

List using `GET /api/v1/notes` with query parameters `owner_id`, `owner_email`,
`resource_id`, and optional `limit` (1-100). Delete using
`DELETE /api/v1/notes/{id}` with `owner_id` and `owner_email` query parameters.

Saved notes belong to the matched LifeAdmin user, plus their source/lesson scope.
Reusing a request ID returns the original note. Titles accept 1-200 characters
and content 1-20,000. The service key is privileged and must stay on the backend;
end users should use the Bearer-token endpoints above.

## Connect from Docker or another device

For PyLearn in Docker on the same computer:

```dotenv
LIFEADMIN_DOCKER_API_URL=http://host.docker.internal:8001
LIFEADMIN_API_KEY=<same-generated-secret>
```

For a manually run PyLearn backend, use
`LIFEADMIN_API_URL=http://127.0.0.1:8001`. For another device, replace the host
with LifeAdmin's LAN IP. Bind the API to `0.0.0.0` and allow TCP 8001 through the
host firewall. Never use `0.0.0.0` as the destination URL. Use HTTPS or a private
encrypted network outside a trusted LAN.

Run tests using `python -m pytest tests -q` and
`python scripts/smoke_ui.py`. Databases, backups, `.env` and the virtual environment
are ignored by Git. Push this project separately from PyLearn.

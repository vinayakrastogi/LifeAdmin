# Shared cloud database

The Streamlit UI and FastAPI API remain part of the independent LifeAdmin project.
Both now support the same PostgreSQL database, even when deployed on different hosts.
edT continues to communicate only over the LifeAdmin HTTP API.

## Current demonstration deployment

- Interface: https://lifeadmin-vinayakrastogi.onrender.com
- API: https://lifeadmin-api-vinayakrastogi.onrender.com
- API documentation: https://lifeadmin-api-vinayakrastogi.onrender.com/docs
- Repository: https://github.com/vinayakrastogi/LifeAdmin (private)

The interface and API are two **native Python Free web services** in Render's Singapore
region, sharing LifeAdmin's own Neon project. Neither uses Docker. edT uses a separate
Neon project and calls the LifeAdmin API over HTTPS. The original source repository
remains configured as the local Git `upstream`; this deployment copy is `origin`.
Existing local accounts, notes, sessions and document metadata were migrated from a
read-only SQLite snapshot. Local uploads were not copied to cloud storage.

## Database configuration

1. Create a separate free Neon project for LifeAdmin (do not reuse edT's database).
2. Copy the **pooled PostgreSQL connection URL**, including `sslmode=require`.
3. Set `LIFEADMIN_DATABASE_URL` to that same secret on both the API host and the UI host.
4. Set `LIFEADMIN_SEED_DEMO_USERS=true` on both hosts for the presentation accounts.

Users, password hashes, sessions, notes, document metadata and reminders are stored in
PostgreSQL. User ownership checks are unchanged. Schema initialization and demo seeding
use PostgreSQL transaction locks so simultaneous UI/API startup is safe.

Leaving `LIFEADMIN_DATABASE_URL` blank retains the local SQLite database. An invalid URL
or unavailable PostgreSQL server raises an error; the app does not silently switch to SQLite.
Only the LifeAdmin-specific variable is used; edT's `DATABASE_URL` is unrelated.

## Fresh deployment

For a fresh demonstration database, start both services with the URL and demo seeding
enabled. They create the schema and the following accounts automatically:

| Email | Password |
|---|---|
| demostudent@example.com | demostudent |
| demofaculty@example.com | demofaculty |

On Render, deploy the API using the native Python runtime, with repository root as root directory:

```sh
pip install -r requirements-api.txt
uvicorn lifeadmin.api:app --host 0.0.0.0 --port "$PORT"
```

Use the first command as the build command, the second as the start command, and `/health`
as the health path. Configure `LIFEADMIN_API_KEY` with the same random secret as edT.
ngrok is unnecessary for an API hosted on Render. LifeAdmin does not require Docker.
The `.python-version` file selects the latest supported Python 3.12 patch on Render;
select Python 3.12 if using Streamlit Community Cloud instead. The API installs
only `requirements-api.txt`; the Streamlit UI installs the full `requirements.txt`.

For the interface, create another **Free Python web service** from the same private repository:

```sh
pip install -r requirements.txt
streamlit run app.py --server.address 0.0.0.0 --server.port "$PORT" --server.headless true --browser.gatherUsageStats false
```

Set the UI health path to `/_stcore/health`. Configure `LIFEADMIN_DATABASE_URL` with the
same PostgreSQL URL as the API and `LIFEADMIN_SEED_DEMO_USERS=true`. The UI does not need
the integration API key. Keep Streamlit's CORS and XSRF protections enabled.

This deployment uses Render for the UI to reuse the GitHub app's repository-scoped access.
Render's 750 monthly free service hours are shared across the workspace, including edT;
idle services sleep, so this setup is intended for intermittent demonstrations. Open the
services before presenting to allow time for cold starts.

Alternatively, deploy `app.py` on Streamlit Community Cloud. Add these **root-level** entries to its
Secrets settings (actual secrets stay in provider settings):

```toml
LIFEADMIN_DATABASE_URL = "postgresql://USER:PASSWORD@HOST/lifeadmin?sslmode=require"
LIFEADMIN_SEED_DEMO_USERS = "true"
```

Streamlit exports root-level secrets as environment variables. API keys used only by the
integration API do not need to be added to the UI service.
Private GitHub repositories require Streamlit's additional private-repository authorization.

## Preserve an existing local database

Stop the local UI and API to get a consistent source database. Disable demo seeding on
the destination services and do not start them yet. Set `LIFEADMIN_DATABASE_URL` in the
local environment to the empty destination database, then run:

```sh
python scripts/migrate_to_postgres.py --source data/lifeadmin.db
```

This reads the SQLite source without modifying it, imports all tables in one transaction,
preserves user/note IDs and password/session hashes, and advances PostgreSQL ID sequences.
It refuses a destination containing data. Do not run the reset script against a hosted
database; that operation is intentionally disabled. Re-enable demo seeding after migration
if desired, then start both services with the same cloud URL.

## Presentation limitation: files remain temporary

No persistent upload storage was implemented. Document metadata survives in PostgreSQL,
but uploaded originals/thumbnails remain on the UI host's temporary filesystem. After a
restart they may need re-uploading; API and UI hosts do not share these files. Notes and
accounts are in the database and do survive restarts.

## Verification

```sh
python -m pytest tests -q
# Optional: use only a disposable PostgreSQL test database. Tests use random schemas.
LIFEADMIN_TEST_DATABASE_URL=postgresql://USER:PASSWORD@localhost/test_db python -m pytest tests -q
```

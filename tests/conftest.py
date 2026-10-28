import pytest
import os
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from lifeadmin import auth, database, notes


@pytest.fixture(autouse=True)
def local_user(tmp_path, monkeypatch):
    # Never connect test cases to the real deployment database.
    monkeypatch.delenv("LIFEADMIN_DATABASE_URL", raising=False)
    test_url = os.environ.get("LIFEADMIN_TEST_DATABASE_URL")
    engine = None
    if test_url:
        # A disposable schema per test; no test ever resets the real app's schema.
        url = make_url(test_url).set(drivername="postgresql+psycopg2")
        engine = create_engine(url)
        schema = "test_" + uuid4().hex
        with engine.begin() as conn:
            conn.exec_driver_sql(f"CREATE SCHEMA {schema}")
        monkeypatch.setenv("LIFEADMIN_DATABASE_URL", url.update_query_dict(
            {"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False))
    monkeypatch.setenv("LIFEADMIN_SEED_DEMO_USERS", "false")
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "lifeadmin.db")
    auth.init_auth()
    notes.init_notes()
    user = auth.create_user("demostudent@example.com", "demostudent", "Demo Student")
    database.set_current_user(user["id"])
    yield user
    database.set_current_user(None)
    if engine:
        with engine.begin() as conn:
            conn.exec_driver_sql(f"DROP SCHEMA {schema} CASCADE")
        engine.dispose()

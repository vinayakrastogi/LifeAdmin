"""Headless check that every Streamlit page renders without errors."""
import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["LIFEADMIN_DB"] = str(Path(tempfile.mkdtemp()) / "smoke.db")

from streamlit.testing.v1 import AppTest

from lifeadmin import database as db
from lifeadmin import notes
from lifeadmin import auth
from lifeadmin.pipeline import analyse_file

root = Path(__file__).resolve().parent.parent
auth.init_auth()
notes.init_notes()
user = auth.create_user("demostudent@example.com", "demostudent", "Demo Student")
token = auth.login("demostudent@example.com", "demostudent")
db.set_current_user(user["id"])
notes.create_note(user_id=user["id"], source_app="pylearn", owner_id="pylearn:1", resource_id="python/loops",
                  request_id="smoke-test", title="Python loops", content="Remember range(3).")
for p in sorted((root / "sample_docs").glob("*.pdf")):
    doc, _, _ = analyse_file(p)
    db.add_document(doc)

for page in ["Dashboard", "Upload", "Documents", "Reminders", "Notes"]:
    at = AppTest.from_file(str(root / "app.py"), default_timeout=30)
    at.session_state["nav"] = page
    at.session_state["auth_token"] = token
    at.run()
    assert not at.exception, (page, at.exception)
    print("OK:", page)

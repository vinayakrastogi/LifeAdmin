"""UI actions must keep using the existing account-scoped persistence."""
from datetime import date, timedelta
from pathlib import Path

from streamlit.testing.v1 import AppTest

from lifeadmin import auth, database as db, notes
from lifeadmin.models import Document

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def signed_in(page="Dashboard"):
    at = AppTest.from_file(APP, default_timeout=20)
    at.session_state["auth_token"] = auth.login("demostudent@example.com", "demostudent")
    at.session_state["nav"] = page
    return at.run()


def test_all_pages_and_timeline_views_render(local_user):
    db.add_document(Document("policy.pdf", "Insurance", expiry_date=date.today()+timedelta(days=4)))
    for page in ["Dashboard", "Upload", "Documents", "Reminders", "Calendar", "Notes"]:
        at = signed_in(page)
        assert not at.exception, (page, at.exception)
    for view in ["Week", "Month", "Year"]:
        at = signed_in()
        at.session_state["timeline_view"] = view
        at.run()
        assert not at.exception, (view, at.exception)


def test_document_edit_reminder_completion_restore_and_delete(local_user):
    doc_id = db.add_document(Document("review-only.txt", "Bill", expiry_date=date.today()+timedelta(days=3)))
    at = signed_in("Documents")
    next(w for w in at.text_area if w.label == "Notes").set_value("Updated through the detail panel")
    at.button(key=f"FormSubmitter:edit_{doc_id}-Update Document").click().run()
    assert not at.exception
    db.set_current_user(local_user["id"])
    assert db.get_document(doc_id).notes == "Updated through the detail panel"
    at.radio(key="nav").set_value("Reminders").run()
    at.button(key=f"done_{doc_id}").click().run()
    assert not at.exception
    db.set_current_user(local_user["id"])
    assert doc_id in db.completed_ids()
    at.session_state["remtab_sel"] = "Completed"
    at.run()
    at.button(key=f"restore_{doc_id}").click().run()
    assert not at.exception
    db.set_current_user(local_user["id"])
    assert doc_id not in db.completed_ids()
    at.radio(key="nav").set_value("Documents").run()
    at.button(key=f"del_{doc_id}").click().run()
    assert not at.exception
    db.set_current_user(local_user["id"])
    assert db.get_document(doc_id) is None


def test_notes_save_delete_and_calendar_controls(local_user):
    at = signed_in("Notes")
    next(w for w in at.text_input if w.label == "Title").set_value("UI regression note")
    next(w for w in at.text_area if w.label == "Note").set_value("<script>literal text only</script>")
    at.button(key="FormSubmitter:new_note-Save note").click().run()
    assert not at.exception
    saved = notes.list_notes(local_user["id"])
    assert len(saved) == 1 and saved[0]["content"] == "<script>literal text only</script>"
    assert any("&lt;script&gt;literal text only&lt;/script&gt;" in w.value for w in at.markdown)
    at.button(key=f'delete_note_{saved[0]["id"]}').click().run()
    assert not at.exception
    assert notes.list_notes(local_user["id"]) == []
    at.radio(key="nav").set_value("Calendar").run()
    at.button(key="cal_next").click().run()
    assert at.session_state["cal_off"] == 1 and not at.exception
    at.button(key="cal_prev").click().run()
    assert at.session_state["cal_off"] == 0 and not at.exception

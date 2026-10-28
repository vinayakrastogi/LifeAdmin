from pathlib import Path

from streamlit.testing.v1 import AppTest

from lifeadmin import auth, notes

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def test_login_gate_notes_are_private_and_logout_clears_session(local_user):
    notes.create_note(user_id=local_user["id"], source_app="pylearn", owner_id="pylearn:1",
                      resource_id="python/loops", request_id="private-note",
                      title="Private demo lesson", content="This belongs to the demo learner.")
    other = auth.create_user("other@example.com", "OtherPassword123!", "Other Learner")
    at = AppTest.from_file(APP, default_timeout=20).run()
    assert not at.exception
    assert at.title[0].value == "Welcome to LifeAdmin"
    assert len(at.radio) == 0
    at.text_input(key="login_email").set_value("demostudent@example.com")
    at.text_input(key="login_password").set_value("wrong-password")
    at.button(key="FormSubmitter:login_form-Log in").click().run()
    assert at.error[0].value == "Invalid email or password."
    at.text_input(key="login_password").set_value("demostudent")
    at.button(key="FormSubmitter:login_form-Log in").click().run()
    assert not at.exception
    at.radio(key="nav").set_value("Notes").run()
    assert any(item.value == "Private demo lesson" for item in at.subheader)
    at.button(key="logout").click().run()
    assert not at.exception
    assert at.title[0].value == "Welcome to LifeAdmin"
    assert len(at.radio) == 0
    at.text_input(key="login_email").set_value("other@example.com")
    at.text_input(key="login_password").set_value("OtherPassword123!")
    at.button(key="FormSubmitter:login_form-Log in").click().run()
    at.radio(key="nav").set_value("Notes").run()
    assert not at.exception
    assert not any(item.value == "Private demo lesson" for item in at.subheader)
    assert notes.list_notes(other["id"]) == []


def test_registration_signs_in_without_showing_another_users_data():
    at = AppTest.from_file(APP, default_timeout=20).run()
    at.text_input(key="register_name").set_value("New Learner")
    at.text_input(key="register_email").set_value("new@example.com")
    at.text_input(key="register_password").set_value("NewPassword123!")
    at.text_input(key="register_confirmation").set_value("NewPassword123!")
    at.button(key="FormSubmitter:register_form-Create account").click().run()
    assert not at.exception
    assert auth.session_user(at.session_state["auth_token"])["email"] == "new@example.com"
    assert len(at.radio) == 1

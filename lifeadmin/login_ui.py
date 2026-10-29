"""Streamlit authentication gate: no application data renders before sign-in."""
import streamlit as st

from . import auth, database as db
from .style import brand, health_ring, html, pill


def require_login() -> dict:
    db.set_current_user(None)
    user = auth.session_user(st.session_state.get("auth_token"))
    if user:
        db.set_current_user(user["id"])
        return user
    st.session_state.pop("auth_token", None)
    with st.container(key="auth_shell"):
        brand_col, form_col = st.columns([1.08, 1], gap="large")
        with brand_col:
            html('<div class="la-auth-brand">'+brand()+'<div class="la-eyebrow">Your personal document vault</div>'
                 '<h2>Your documents,<br/>all in one place.</h2><p>Keep important files, deadlines and learning notes together. A little more organised, every day.</p>'
                 +pill("none", "A calmer kind of organised")+health_ring(100,"A fresh start")+'</div>')
        with form_col, st.container(key="auth_card"):
            st.title("Welcome to LifeAdmin")
            st.write("Sign in to manage your own documents and notes.")
            login_tab, register_tab = st.tabs(["Log in", "Create account"])
            with login_tab:
                with st.form("login_form"):
                    email = st.text_input("Email", key="login_email")
                    password = st.text_input("Password", type="password", key="login_password")
                    if st.form_submit_button("Log in", type="primary", width="stretch"):
                        try:
                            token = auth.login(email, password)
                            st.session_state.clear()
                            st.session_state["auth_token"] = token
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))
                st.caption("Demo student: demostudent@example.com / demostudent")
                st.caption("Demo faculty: demofaculty@example.com / demofaculty")
            with register_tab:
                with st.form("register_form"):
                    name = st.text_input("Name", key="register_name", max_chars=100)
                    email = st.text_input("Email", key="register_email")
                    password = st.text_input("Password", type="password", key="register_password", max_chars=128)
                    confirmation = st.text_input("Confirm password", type="password", key="register_confirmation", max_chars=128)
                    if st.form_submit_button("Create account", type="primary", width="stretch"):
                        try:
                            if password != confirmation:
                                raise ValueError("Passwords do not match.")
                            auth.create_user(email, password, name)
                            token = auth.login(email, password)
                            st.session_state.clear()
                            st.session_state["auth_token"] = token
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))
                st.caption("Use your PyLearn email to see lesson notes saved from PyLearn.")
    st.stop()


def logout() -> None:
    token = st.session_state.get("auth_token")
    if token:
        auth.logout(token)
    st.session_state.clear()
    db.set_current_user(None)


def user_action(function, *args) -> None:
    """Callbacks execute before the next script run; validate their session again."""
    user = auth.session_user(st.session_state.get("auth_token"))
    if not user:
        db.set_current_user(None)
        return
    db.set_current_user(user["id"])
    function(*args)

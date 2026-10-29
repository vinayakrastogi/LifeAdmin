"""LifeAdmin - Smart Personal Document & Deadline Manager.

Run:  streamlit run app.py
"""
from __future__ import annotations

import dataclasses
from uuid import uuid4
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import plotly.graph_objects as pgo
import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from lifeadmin import database as db
from lifeadmin import demo
from lifeadmin import notes
from lifeadmin import auth
from lifeadmin.demo_accounts import seed_if_enabled
from lifeadmin.login_ui import require_login, logout, user_action
from lifeadmin.export import documents_dataframe, to_csv, to_ics
from lifeadmin.extractor import ALLOWED_EXTENSIONS, MAX_FILE_MB, extract_text, ocr_available
from lifeadmin.health import checks, collection_score, health_score, timeliness_score, verdict
from lifeadmin.models import DOC_TYPES, Document
from lifeadmin.pipeline import analyse_file, analyse_upload, store_upload
from lifeadmin.preview import file_size, friendly_title, human_size, mask_number, thumbnail
from lifeadmin.reminders import (dashboard_counts, needing_attention, overdue, status_of,
                                 upcoming)
from lifeadmin.style import (C, PILL, TYPE_STYLE, avatar_css, brand, card_title, esc, fields_table,
                             file_badge, health_meter, html, icon, inject_styles, kpi, legend,
                             month_calendar, motto, page_header, pill, promo, row, rows,
                             summary_grid, thumb_img, type_tile, health_ring, vault_summary,
                             stat_tiles, result_card, document_row, day_strip)

st.set_page_config(page_title="LifeAdmin", page_icon="🐙", layout="wide",
                   initial_sidebar_state="collapsed")
inject_styles()
auth.init_auth()
seed_if_enabled()
notes.init_notes()
signed_in_user = require_login()

ROOT = Path(__file__).resolve().parent
TODAY = date.today()
PAGES = ["Dashboard", "Upload", "Documents", "Reminders", "Calendar", "Notes"]
NAV_ICONS = {"Dashboard": ":material/home:", "Upload": ":material/cloud_upload:",
             "Documents": ":material/description:", "Reminders": ":material/notifications:",
             "Notes": ":material/edit_note:", "Calendar": ":material/calendar_month:"}
QUICK = {  # Quick Upload tiles -> accepted extensions
    "pdf": ("PDF Document", [".pdf"], "x.pdf"),
    "image": ("Image File", [".png", ".jpg", ".jpeg"], "x.png"),
    "word": ("Word Document", [".docx"], "x.docx"),
    "excel": ("Excel Sheet", [".xlsx"], "x.xlsx"),
}
PLOT_CFG = {"displayModeBar": False}


# ================================================================ helpers
def go(page: str, **state) -> None:
    """Navigation callback (runs before the next rerun)."""
    st.session_state.nav = page
    for k, v in state.items():
        st.session_state[k] = v


def fmt(d: Optional[date]) -> str:
    return d.strftime("%b %d, %Y") if d else "—"


def uploaded_on(doc: Document) -> Optional[date]:
    try:
        return datetime.fromisoformat(doc.uploaded_at).date()
    except (TypeError, ValueError):
        return None


def first_name(name: str) -> str:
    return (name.split() or ["there"])[0]


def initials(name: str) -> str:
    parts = [p for p in name.split() if p]
    return ("".join(p[0] for p in parts[:2]) or "?").upper()


def greeting() -> str:
    h = datetime.now().hour
    return "Good Morning" if h < 12 else "Good Afternoon" if h < 17 else "Good Evening"


def haystack(d: Document) -> str:
    return f"{d.filename} {d.doc_type} {d.doc_number} {d.organization} {d.holder_name} {d.vehicle_no}".lower()


def pill_for(doc: Document, completed: set = frozenset(), upcoming_label: bool = False) -> str:
    if doc.id in completed:
        return pill("completed")
    level = status_of(doc).level
    if upcoming_label and level == "active":
        return pill("upcoming")
    return pill(level)


def days_note(doc: Document) -> str:
    s = status_of(doc)
    if s.days is None:
        return ""
    if s.days < 0:
        return '<b style="color:#F87171">(Overdue)</b>'
    if s.days == 0:
        return '<b style="color:#F87171">(Due today)</b>'
    color = "#F87171" if s.days <= 7 else "#AEB5D6"
    return f'<b style="color:{color}">({s.days} day{"s" if s.days != 1 else ""} left)</b>'


def card_header(title: str, icon_name: str, target: Optional[str] = None, key: str = "") -> None:
    if not target:
        html(card_title(title, icon_name))
        return
    a, b = st.columns([3, 1], vertical_alignment="center")
    with a:
        html(card_title(title, icon_name))
    with b, st.container(key=f"viewall_{key or title.replace(' ', '_').lower()}"):
        st.button("View All →", key=f"va_{key or title}", type="tertiary", on_click=go, args=(target,))


def load_demo() -> None:
    """Load (or refresh) the 24 demo documents, dated relative to today."""
    user = auth.session_user(st.session_state.get("auth_token"))
    if not user:
        return
    db.set_current_user(user["id"])
    n = demo.load_demo()
    st.session_state["_toast"] = f"Loaded {n} demo documents"


def status_block(doc: Document) -> str:
    s = status_of(doc)
    return (f'<div style="display:flex;gap:.6rem;align-items:center;margin:.2rem 0 .6rem 0">{pill(s.level)}'
            f'<span class="la-sub">{esc(s.message)} {esc(s.action)}</span></div>')


def doc_fields(doc: Document) -> List[tuple]:
    pairs = [("Name", doc.holder_name), ("Document type", doc.doc_type),
             ("Document No", mask_number(doc.doc_number)), ("Organization", doc.organization),
             ("Vehicle No", doc.vehicle_no), ("Amount", doc.amount),
             ("Valid from", fmt(doc.start_date) if doc.start_date else ""),
             ("Valid until / Due", fmt(doc.expiry_date) if doc.expiry_date else "")]
    return [(k, v) for k, v in pairs if v]


def doc_form(doc: Document, key: str, submit_label: str) -> Optional[Document]:
    """Review & correction form - extraction is never perfect. Returns Document or None."""
    with st.form(key, border=False):
        c1, c2 = st.columns(2)
        doc_type = c1.selectbox("Document type", DOC_TYPES,
                                index=DOC_TYPES.index(doc.doc_type) if doc.doc_type in DOC_TYPES else len(DOC_TYPES) - 1)
        holder = c2.text_input("Holder name", doc.holder_name)
        org = c1.text_input("Organization", doc.organization)
        number = c2.text_input("Document number", doc.doc_number)
        vehicle = c1.text_input("Vehicle number", doc.vehicle_no)
        amount = c2.text_input("Amount", doc.amount)
        d1, d2 = st.columns(2)
        has_start = d1.checkbox("Has start date", value=doc.start_date is not None, key=f"{key}_hs")
        start = d1.date_input("Start date", doc.start_date or TODAY, format="DD/MM/YYYY", key=f"{key}_sd")
        has_exp = d2.checkbox("Has expiry / due date", value=doc.expiry_date is not None, key=f"{key}_he")
        expiry = d2.date_input("Expiry / due date", doc.expiry_date or TODAY, format="DD/MM/YYYY", key=f"{key}_ed")
        notes = st.text_area("Notes", doc.notes, height=80)
        submitted = st.form_submit_button(submit_label, type="primary", width="stretch")
    if not submitted:
        return None
    doc = dataclasses.replace(doc)
    doc.doc_type, doc.holder_name, doc.organization = doc_type, holder.strip(), org.strip()
    doc.doc_number, doc.vehicle_no, doc.amount = number.strip(), vehicle.strip().upper(), amount.strip()
    doc.start_date = start if has_start else None
    doc.expiry_date = expiry if has_exp else None
    doc.notes = notes.strip()
    return doc


REMINDER_TEXT = {
    "Insurance": "Renew your {org} policy before it lapses.",
    "ID": "Renew this ID before it expires.",
    "Vehicle": "Renew this vehicle document to stay road-legal.",
    "Bill": "Pay {amount} before the due date.",
    "Warranty": "Book any repairs while the warranty is still valid.",
    "Subscription": "Renew or cancel before the next billing date.",
    "Certificate": "Renew or re-validate this certificate.",
}


def reminder_text(doc: Document) -> str:
    t = REMINDER_TEXT.get(doc.doc_type)
    if not t:
        return status_of(doc).action
    return t.format(org=doc.organization or "insurance", amount=doc.amount or "the bill")


# ================================================================ chrome
def sidebar() -> None:
    if "nav" not in st.session_state:
        st.session_state.nav = "Dashboard"
    with st.sidebar:
        html(brand())
        st.radio("Navigation", PAGES, key="nav", label_visibility="collapsed",
                 format_func=lambda p: f"{NAV_ICONS[p]} {p}")
        with st.container(key="sidebar_footer"):
            html(f'<div class="la-user"><div class="la-user-icon">{esc(initials(signed_in_user["name"]))}</div>'
                 f'<div><b>{esc(signed_in_user["name"])}</b><small>Personal workspace</small></div></div>')
            st.caption(signed_in_user["email"])
            st.button("Log out", on_click=logout, key="logout", width="stretch")
            html(motto())


def topbar(docs: List[Document], completed: set, user: str) -> None:
    urgent = [d for d in needing_attention(docs) if d.id not in completed]
    page = st.session_state.nav
    titles = {"Dashboard": ("Overview", f"Welcome back, {first_name(user)}."),
              "Upload": ("Upload documents", "A new home for your important files."),
              "Documents": ("Your documents", "Everything important, within reach."),
              "Reminders": ("Reminders", "A little ahead of every deadline."),
              "Calendar": ("Calendar", "Your dates, all in view."),
              "Notes": ("Notes", "Your thoughts and PyLearn lesson notes.")}
    title, subtitle = titles[page]
    with st.container(key="topbar"):
        heading, search, upload, bell, avatar = st.columns([4.7, 2.6, 1.2, .6, .6], vertical_alignment="center")
        with heading:
            html(page_header(title, subtitle, "Vault"))
        with search, st.container(key="topsearch"):
            st.text_input("Search documents", key="q", placeholder="Search your vault", label_visibility="collapsed")
        with upload:
            st.button("Upload", type="primary", icon=":material/add:", key="top_upload", on_click=go, args=("Upload",), width="stretch")
        with bell, st.container(key="bell_on" if urgent else "bell_off"):
            with st.popover(":material/notifications:"):
                st.markdown("**Notifications**")
                if not urgent:
                    st.caption("You're all caught up.")
                for d in urgent[:6]:
                    status = status_of(d)
                    html(row(type_tile(d.doc_type, 32), friendly_title(d.filename), esc(status.message), pill(status.level)))
                if urgent:
                    st.button("Open Reminders", key="bell_open", on_click=go, args=("Reminders",), width="stretch")
        with avatar:
            avatar_css(initials(user))
            with st.container(key="avatar"), st.popover(first_name(user)):
                with st.form("profile", border=False):
                    name = st.text_input("Your name", user)
                    if st.form_submit_button("Save", type="primary"):
                        try:
                            db.set_user_name(name)
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))
                st.divider()
                st.markdown("**Demo data**")
                st.caption("24 sample documents. Loading them keeps your own documents.")
                st.button("Load demo documents", key="demo_menu", icon=":material/science:", on_click=load_demo, width="stretch")
                st.button("Log out", on_click=logout, key="profile_logout", width="stretch")
                st.caption("Your vault is private to your account.")


def search_results(docs: List[Document], q: str) -> None:
    hits = [d for d in docs if q.lower() in haystack(d)]
    with st.container(key="card_search"):
        card_header(f'Search results for "{q}"', "search", "Documents", key="search")
        html(rows([document_row(d, pill_for(d)) for d in hits[:5]], "No documents match your search."))


@st.fragment(run_every="60s")
def dashboard_live_header() -> None:
    html('<div class="la-eyebrow">Your vault · Updated now</div>')


@st.fragment(run_every="60s")
def dashboard_timeline(docs: List[Document], completed: set) -> None:
    with st.container(key="card_timeline"):
        html(card_title("Your timeline", "calendar"))
        view = st.segmented_control("Timeline view", ["Week", "Month", "Year"], default="Week", key="timeline_view", label_visibility="collapsed") or "Week"
        html(day_strip(docs, completed, date.today(), view))
        st.caption("Dashed rings are pending deadlines. Solid rings are handled.")


# ================================================================ pages
def page_dashboard(docs: List[Document], completed: set, user: str) -> None:
    dashboard_live_header()
    c = dashboard_counts(docs)
    score = collection_score(docs)
    pending = [d for d in needing_attention(docs) if d.id not in completed]
    next_up = [d for d in upcoming(docs) if d.id not in completed]
    next_days = (next_up[0].expiry_date-date.today()).days if next_up else None
    with st.container(key="layout_dashboard"):
        health_col, summary_col = st.columns([1, 2], gap="medium")
        with health_col, st.container(key="card_health"):
            html(card_title("Document health", "shield"))
            html(pill("none", "On track" if score >= 80 else "Needs attention"))
            html(health_ring(score))
            st.caption("Completeness and timeliness, together.")
        with summary_col:
            html(vault_summary(c["active"], c["total"], next_days))
            html(stat_tiles([("Needs attention", len(pending)), ("Due this month", sum(bool(d.expiry_date and d.expiry_date.year == date.today().year and d.expiry_date.month == date.today().month and d.id not in completed) for d in docs)), ("Handled", len(completed))]))
        timeline, insight = st.columns([2, 1], gap="medium")
        with timeline:
            dashboard_timeline(docs, completed)
        with insight, st.container(key="card_insight"):
            html(f'<div class="la-insight"><b>{len(pending)}</b><p>{"A few documents need your attention. A small step now can clear your next deadline." if pending else "Everything is in view. Keep your documents current as new dates come in."}</p></div>')
            card_header("Next up", "clock", "Reminders", key="next")
            html(rows([row(type_tile(d.doc_type, 34), friendly_title(d.filename), fmt(d.expiry_date), pill_for(d, completed)) for d in next_up[:3]], "No upcoming deadlines."))
        with st.container(key="card_recent"):
            card_header("Recently added", "files", "Documents", key="recent")
            html(rows([document_row(d, pill_for(d, completed)) for d in docs[:6]], "Your vault starts with one document."))
            if not docs:
                st.button("Load demo documents", key="demo", on_click=load_demo)


def page_upload(docs: List[Document]) -> None:
    saved: Dict[str, int] = st.session_state.setdefault("saved_uploads", {})
    cache: Dict[str, dict] = st.session_state.setdefault("analysis", {})
    filt = st.session_state.get("qfilter")
    exts = QUICK[filt][1] if filt else sorted(ALLOWED_EXTENSIONS)
    names = ", ".join(e.strip(".").upper() for e in exts if e != ".jpeg")
    st.markdown(f'<style>.st-key-card_drop{{--la-supports:"Supports {names} (Max {MAX_FILE_MB}MB)";}}</style>',
                unsafe_allow_html=True)

    with st.container(key="layout_upload"):
        left, right = st.columns([1.45, 1], gap="medium")
        with left:
            with st.container(key="card_drop"):
                files = st.file_uploader("Upload documents", type=[e.strip(".") for e in exts],
                                         accept_multiple_files=True, key=f"uploader_{filt or 'all'}",
                                         label_visibility="collapsed") or []

            def fkey(f) -> str:
                return f"{f.name}:{f.size}"

            def analysis(f) -> dict:
                k = fkey(f)
                if k not in cache:
                    data = f.getvalue()
                    try:
                        skeleton = st.empty()
                        skeleton.markdown('<div class="la-skeleton" aria-label="Extracting document"></div>', unsafe_allow_html=True)
                        with st.spinner("Reading your document…"):
                            doc, text, conf = analyse_upload(data, f.name)
                        skeleton.empty()
                        cache[k] = {"doc": doc, "text": text, "conf": conf, "thumb": thumbnail(data, f.name),
                                    "at": TODAY}
                    except Exception as e:  # unreadable / invalid file
                        cache[k] = {"error": str(e)}
                return cache[k]

            current = None
            if files:
                with st.container(key="card_review"):
                    html(card_title("Review & Save", "sparkle"))
                    pick = files[0]
                    if len(files) > 1:
                        pick = st.selectbox("File to review", files, key="review_pick",
                                            format_func=lambda f: f"{f.name}{'  ✓ saved' if fkey(f) in saved else ''}")
                    info = analysis(pick)
                    current = (pick, info)
                    if "error" in info:
                        st.error(info["error"])
                    elif fkey(pick) in saved:
                        html(result_card("DONE", f"{pick.name} is saved to your vault."))
                        st.button("Open in Documents", key="open_saved", on_click=go,
                                  args=("Documents",), kwargs={"doc_pick": saved[fkey(pick)]})
                    else:
                        doc: Document = info["doc"]
                        if not info["text"].strip():
                            hint = "" if ocr_available() else " (install Tesseract to read scanned images)"
                            st.warning(f"No text could be read from this file{hint}. Fill in the fields below.")
                        else:
                            st.caption(f"Detected **{doc.doc_type}** with **{int(info['conf'] * 100)}%** confidence — "
                                       "check the pre-filled fields before saving.")
                        html(status_block(doc))
                        edited = doc_form(doc, f"review_{fkey(pick)}", "Save Document")
                        if edited:
                            edited.stored_path = store_upload(pick.getvalue(), pick.name)
                            saved[fkey(pick)] = db.add_document(edited)
                            st.session_state["_toast"] = f"Saved {pick.name}"
                            st.rerun()

            with st.container(key="card_quick"):
                html(card_title("Quick Upload", "sparkle"))
                cols = st.columns(4)
                for col, (k, (label, _, sample)) in zip(cols, QUICK.items()):
                    with col, st.container(key=f"qtsel_{k}" if filt == k else f"qt_{k}"):
                        html(f'<div class="la-qt">{file_badge(sample, 36)}</div>')
                        st.button(label, key=f"qbtn_{k}", type="tertiary",
                                  on_click=lambda k=k: st.session_state.update(qfilter=None if filt == k else k))
                st.caption("Pick a tile to accept only that file type; pick it again to accept everything.")

        with right:
            with st.container(key="card_uploads"):
                card_header("Recent Uploads", "file", "Documents", key="uploads")
                items = []
                for f in files:
                    if fkey(f) not in saved:
                        items.append(row(file_badge(f.name), f.name, f"Just now • {human_size(f.size)}", pill("pending")))
                for d in docs:
                    size = human_size(file_size(d.stored_path))
                    items.append(row(file_badge(d.filename), d.filename,
                                     f"{fmt(uploaded_on(d))}{' • ' + size if size else ''}", pill("processed")))
                html(rows(items[:5], "Nothing uploaded yet."))

            with st.container(key="card_extract"):
                card_header("Extracted Information", "sparkle")
                subject = raw = None
                if current and "doc" in current[1] and fkey(current[0]) not in saved:
                    subject, raw = current[1]["doc"], current[1]["text"]
                    thumb, when, state = current[1]["thumb"], TODAY, "pending"
                elif docs:
                    subject = docs[0]
                    path = subject.stored_path
                    data = Path(path).read_bytes() if path and Path(path).exists() else None
                    thumb = thumbnail(data, subject.filename) if data else None
                    when, state = uploaded_on(subject), "processed"
                if subject is None:
                    html('<div class="la-empty">Upload a document to see what LifeAdmin finds in it.</div>')
                else:
                    html(f'<div class="la-extract">{thumb_img(thumb)}<div style="flex:1;min-width:0">'
                         f'<div class="t" style="font-weight:700;color:#fff;font-size:.92rem;word-break:break-all">{esc(subject.filename)}</div>'
                         f'<div class="la-sub" style="margin:.2rem 0 .5rem 0">Extracted on {fmt(when)}</div>{pill(state)}</div></div>')
                    html(result_card("EXTRACTED", "Review the details before you save."))
                    html(fields_table(doc_fields(subject)))
                    with st.container(key="viewdetails"), st.popover("View Details", icon=":material/visibility:"):
                        html(health_meter(health_score(subject), checks(subject), verdict(health_score(subject))))
                        if raw is None and subject.stored_path and Path(subject.stored_path).exists():
                            try:
                                raw = extract_text(subject.stored_path)
                            except Exception:
                                raw = ""
                        st.markdown("**Extracted text**")
                        st.code((raw or "(nothing extracted)")[:3000], language=None)

def page_documents(docs: List[Document], completed: set) -> None:
    if not docs:
        st.info("Your vault is empty. Go to Upload to add your first document.")
        return
    q = (st.session_state.get("q") or "").strip().lower()
    with st.container(key="doctabs"):
        status = st.segmented_control("Status", ["All", "Active", "Expiring Soon", "Critical", "Overdue", "No Expiry", "Handled"],
                                      default="All", key="doc_status", label_visibility="collapsed") or "All"
    types = st.multiselect("Document type", DOC_TYPES, placeholder="All document types")
    level_of = {"Active": "active", "Expiring Soon": "warning", "Critical": "critical", "Overdue": "expired", "No Expiry": "none"}
    shown = [d for d in docs if (status == "All" or (status == "Handled" and d.id in completed)
             or (status in level_of and status_of(d).level == level_of[status]))
             and (not types or d.doc_type in types) and (not q or q in haystack(d))]
    if not shown:
        st.info("No documents match these filters.")
        return
    ids = [d.id for d in shown]
    if st.session_state.get("doc_pick") not in ids:
        st.session_state.pop("doc_pick", None)
    by_id = {d.id: d for d in shown}
    with st.container(key="layout_documents"):
        listing, detail = st.columns([2, 1.1], gap="medium")
        with listing, st.container(key="card_document_list"):
            html(card_title(f"Your vault · {len(shown)} documents", "files"))
            pick = st.selectbox("Open document", ids, key="doc_pick", format_func=lambda i: f"DOC-{i:03d} · {by_id[i].filename}")
            for d in shown:
                html(document_row(d, pill_for(d, completed)))
        doc = by_id[pick]
        with detail, st.container(key="card_docdetail"):
            html(f'<div class="la-eyebrow">Document details</div><div class="la-mono">DOC-{doc.id:03d}</div>')
            html(f'<h3>{esc(friendly_title(doc.filename))}</h3><div class="la-sub">{esc(doc.filename)}</div>')
            html(status_block(doc))
            html(fields_table(doc_fields(doc)))
            if doc.notes:
                html(f'<div class="la-note-content">{esc(doc.notes)}</div>')
            with st.expander("Document health"):
                score = health_score(doc)
                html(health_meter(score, checks(doc), verdict(score)))
                st.caption(f"Timeliness: {timeliness_score(doc)}%")
            with st.expander("Edit details"):
                edited = doc_form(doc, f"edit_{doc.id}", "Update Document")
                if edited:
                    db.update_document(edited)
                    st.session_state["_toast"] = "Document updated"
                    st.rerun()
            if doc.stored_path and Path(doc.stored_path).exists():
                st.download_button("Download original", Path(doc.stored_path).read_bytes(), file_name=doc.filename,
                                   icon=":material/download:", width="stretch", key=f"dl_{doc.id}")
            st.download_button("Add to calendar", to_ics([doc]), f"lifeadmin_{doc.id}.ics", "text/calendar", key=f"doc_ics_{doc.id}", width="stretch")
            with st.popover("Delete document", icon=":material/delete:", width="stretch"):
                st.write(f"Permanently delete **{doc.filename}** and its stored file?")
                if st.button("Yes, delete", type="primary", key=f"del_{doc.id}"):
                    db.delete_document(doc.id)
                    st.session_state["_toast"] = "Document deleted"
                    st.rerun()
    with st.container(key="card_activity"):
        html(card_title("Activity history", "history"))
        logs = db.list_logs(100)
        if logs:
            log_df = pd.DataFrame([dict(r) for r in logs])[["created_at", "action", "detail"]]
            log_df.columns = ["When", "Action", "Detail"]
            log_df["When"] = log_df["When"].str.replace("T", "  ", regex=False)
            st.dataframe(log_df, hide_index=True, width="stretch", height=240)
        else:
            html('<div class="la-empty">No activity recorded yet.</div>')


def reminder_feedback(function, doc_id: int) -> None:
    user_action(function, doc_id)
    st.session_state["_toast"] = "Reminder updated"


def reminder_card(d: Document, completed: set) -> None:
    is_done = d.id in completed
    with st.container(key=f"rem_{d.id}"):
        html(f'<div class="la-mono">DOC-{d.id:03d}</div>')
        html(f'<h3>{esc(friendly_title(d.filename))}</h3><div class="la-sub">{esc(reminder_text(d))}</div>')
        html(f'<div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">{pill_for(d,completed)}<span class="la-sub">{fmt(d.expiry_date)}</span></div>')
        html(f'<div class="la-sub">{days_note(d)}</div>')
        small, primary = st.columns([1, 1.5], gap="small")
        with small, st.popover("Not yet" if not is_done else "Options", width="stretch"):
            st.button("Open in Documents", key=f"open_{d.id}", width="stretch", on_click=go, args=("Documents",), kwargs={"doc_pick": d.id, "doc_status": "All"})
            st.download_button("Add to calendar (.ics)", to_ics([d]), f"lifeadmin_{d.id}.ics", "text/calendar", key=f"ics_{d.id}", width="stretch")
        if is_done:
            primary.button("Restore reminder", key=f"restore_{d.id}", width="stretch", on_click=reminder_feedback, args=(db.restore_reminder, d.id))
        else:
            primary.button("Yes, done", key=f"done_{d.id}", type="primary", width="stretch", on_click=reminder_feedback, args=(db.complete_reminder, d.id))


def exports_panel(docs: List[Document], key: str) -> None:
    with st.container(key=f"card_export_{key}"):
        html(card_title("Take your dates with you", "download"))
        c1, c2 = st.columns(2)
        c1.download_button("Export CSV", to_csv(docs), "lifeadmin_documents.csv", "text/csv", icon=":material/table:", width="stretch", key=f"{key}_csv")
        c2.download_button("Export calendar (.ics)", to_ics(docs), "lifeadmin_expiries.ics", "text/calendar", icon=":material/event:", width="stretch", key=f"{key}_ics")
        st.caption("Calendar files include alerts 30 and 7 days before each deadline.")


def page_reminders(docs: List[Document], completed: set) -> None:
    dated = [d for d in docs if d.expiry_date]
    up = [d for d in upcoming(docs) if d.id not in completed]
    od = [d for d in overdue(docs) if d.id not in completed]
    done = sorted((d for d in dated if d.id in completed), key=lambda d: d.expiry_date)
    with st.container(key="remtabs"):
        tab = st.segmented_control("Show", ["All", "Upcoming", "Overdue", "Completed"], default="All", key="remtab_sel", label_visibility="collapsed") or "All"
    if tab == "Completed":
        if not done:
            st.info("Nothing marked as completed yet.")
        for d in done:
            reminder_card(d, completed)
    else:
        seven = [d for d in up if 0 <= (d.expiry_date-date.today()).days <= 7]
        thirty = [d for d in up if 7 < (d.expiry_date-date.today()).days <= 30]
        later = [d for d in up if (d.expiry_date-date.today()).days > 30]
        groups = [("Overdue", od), ("Due in 7 days", seven), ("Due in 30 days", thirty)]
        if tab == "Upcoming":
            groups[0] = ("Later", later)
        if tab == "Overdue":
            groups = [("Overdue", od)]
        with st.container(key="layout_board"):
            columns = st.columns(len(groups), gap="medium")
            for column, (label, items) in zip(columns, groups):
                with column:
                    html(f'<div class="la-eyebrow">{esc(label)} · {len(items)}</div>')
                    if not items:
                        html('<div class="la-empty">All clear here.</div>')
                    for d in items:
                        reminder_card(d, completed)
        if tab == "All" and later:
            with st.expander(f"Later deadlines · {len(later)}"):
                for d in later:
                    reminder_card(d, completed)
    exports_panel(docs, "reminders")


def page_calendar(docs: List[Document], completed: set) -> None:
    dated = [d for d in docs if d.expiry_date]
    off = st.session_state.setdefault("cal_off", 0)
    y, m = divmod(TODAY.year * 12 + TODAY.month - 1 + off, 12)
    m += 1
    selected = sorted([d for d in dated if (d.expiry_date.year,d.expiry_date.month) == (y,m)], key=lambda d: d.expiry_date)
    marks: Dict[date, list] = {}
    for d in dated:
        if d.id not in completed:
            marks.setdefault(d.expiry_date, []).append((C["red"] if status_of(d).level in {"expired","critical"} else C["indigo"], friendly_title(d.filename)))
    with st.container(key="layout_calendar"):
        calendar_col, list_col = st.columns([2,1], gap="medium")
        with calendar_col, st.container(key="card_calendar_large"):
            prev, title, nxt = st.columns([1,4,1], vertical_alignment="center")
            prev.button("Previous", key="cal_prev", on_click=lambda: st.session_state.update(cal_off=off-1), icon=":material/chevron_left:")
            with title:
                html(f'<div class="la-cal-head">{date(y,m,1):%B %Y}</div>')
            nxt.button("Next", key="cal_next", on_click=lambda: st.session_state.update(cal_off=off+1), icon=":material/chevron_right:")
            html(month_calendar(y,m,marks,date.today()))
        with list_col, st.container(key="card_month_deadlines"):
            html(card_title("This month's dates", "calendar"))
            html(rows([row(type_tile(d.doc_type,32),friendly_title(d.filename),fmt(d.expiry_date),pill_for(d,completed)) for d in selected],"No deadlines this month."))
    exports_panel(docs,"calendar")


def page_notes() -> None:
    with st.container(key="layout_notes"):
        compose, saved = st.columns([1, 1.7], gap="medium")
        with compose, st.container(key="card_note_compose"):
            html(card_title("A place for your thoughts", "file"))
            st.caption("Save a personal note or find the lesson notes you wrote in PyLearn.")
            with st.form("new_note", clear_on_submit=True):
                title = st.text_input("Title", max_chars=200)
                content = st.text_area("Note", max_chars=20000)
                if st.form_submit_button("Save note", type="primary", width="stretch"):
                    if not title.strip() or not content.strip():
                        st.error("Enter a title and a note.")
                    else:
                        notes.create_note(user_id=signed_in_user["id"], source_app="lifeadmin", owner_id=str(signed_in_user["id"]), resource_id="personal", request_id=str(uuid4()), title=title.strip(), content=content.strip())
                        st.success("Note saved.")
                        st.toast("Note saved", icon=":material/check_circle:")
        with saved:
            if st.button("Refresh notes", icon=":material/refresh:"):
                st.rerun()
            items = notes.list_notes(signed_in_user["id"], limit=100)
            if not items:
                st.info("No notes yet. Save a note from a PyLearn lesson to see it here.")
            for note in items:
                with st.container(key=f'card_note_{note["id"]}'):
                    st.subheader(note["title"])
                    st.caption("PyLearn lesson" if note["source_app"] == "pylearn" else "Personal note")
                    html(f'<div class="la-note-content">{esc(note["content"])}</div>')
                    st.caption(note["created_at"])
                    if st.button("Delete note", key=f'delete_note_{note["id"]}'):
                        notes.delete_note(note["id"], signed_in_user["id"])
                        st.session_state["_toast"] = "Note deleted"
                        st.rerun()


# ================================================================ main
sidebar()
documents = db.list_documents()
done_ids = db.completed_ids()
user_name = db.get_user_name()
topbar(documents, done_ids, user_name)
if "_toast" in st.session_state:
    st.toast(st.session_state.pop("_toast"), icon=":material/check_circle:")

page = st.session_state.nav
query = (st.session_state.get("q") or "").strip()
if query and page != "Documents":
    search_results(documents, query)

if page == "Dashboard":
    page_dashboard(documents, done_ids, user_name)
elif page == "Upload":
    page_upload(documents)
elif page == "Documents":
    page_documents(documents, done_ids)
elif page == "Notes":
    page_notes()
elif page == "Calendar":
    page_calendar(documents, done_ids)
else:
    page_reminders(documents, done_ids)

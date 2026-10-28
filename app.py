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
                             summary_grid, thumb_img, type_tile)

st.set_page_config(page_title="LifeAdmin", page_icon="🐙", layout="wide",
                   initial_sidebar_state="expanded")
inject_styles()
auth.init_auth()
seed_if_enabled()
notes.init_notes()
signed_in_user = require_login()

ROOT = Path(__file__).resolve().parent
TODAY = date.today()
PAGES = ["Dashboard", "Upload", "Documents", "Reminders", "Notes"]
NAV_ICONS = {"Dashboard": ":material/home:", "Upload": ":material/cloud_upload:",
             "Documents": ":material/description:", "Reminders": ":material/notifications:",
             "Notes": ":material/edit_note:"}
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
            st.caption(signed_in_user["email"])
            st.button("Log out", on_click=logout, key="logout", width="stretch")
            html(motto())


def topbar(docs: List[Document], completed: set, user: str) -> None:
    urgent = [d for d in needing_attention(docs) if d.id not in completed]
    with st.container(key="topbar"):
        _, search, bell, avatar = st.columns([5.4, 3, 0.42, 1.7], vertical_alignment="center")
        with search, st.container(key="topsearch"):
            st.text_input("Search documents", key="q", placeholder="Search documents...",
                          label_visibility="collapsed")
        with bell, st.container(key="bell_on" if urgent else "bell_off"):
            with st.popover(":material/notifications:"):
                st.markdown("**Notifications**")
                if not urgent:
                    st.caption("You're all caught up.")
                for d in urgent[:6]:
                    s = status_of(d)
                    html(row(type_tile(d.doc_type, 32), friendly_title(d.filename), esc(s.message), pill(s.level)))
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
                st.caption("24 sample documents covering overdue, due today, critical, expiring, "
                           "active and no-expiry cases. Your own documents are kept.")
                st.button("Load demo documents", key="demo_menu", icon=":material/science:",
                          on_click=load_demo, width="stretch")
                st.caption("🔒 Everything stays on this computer.")


def search_results(docs: List[Document], q: str) -> None:
    hits = [d for d in docs if q.lower() in haystack(d)]
    with st.container(key="card_search"):
        card_header(f'Search results for "{q}"', "search", "Documents", key="search")
        html(rows([row(file_badge(d.filename), d.filename,
                       f"{esc(d.doc_type)} · Expires {fmt(d.expiry_date)}", pill_for(d)) for d in hits[:5]],
                  "No documents match your search."))


# ================================================================ pages
def page_dashboard(docs: List[Document], completed: set, user: str) -> None:
    html(f'<div class="la-greet"><h1>{greeting()}, {esc(first_name(user))}</h1>'
         f'<p>Here\'s your life at a glance. Stay organized, stay ahead.</p></div>')
    c = dashboard_counts(docs)
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        html(kpi("total", "Total Documents", c["total"], "All your important files"))
    with k2:
        html(kpi("active", "Active", c["active"], "Up to date"))
    with k3:
        html(kpi("expiring", "Expiring Soon", c["expiring"], "Within 30 days"))
    with k4:
        html(kpi("critical", "Critical", c["critical"], "Overdue / Needs attention"))
    st.write("")

    left, right = st.columns([1.55, 1], gap="medium")
    with left:
        with st.container(key="card_health"):
            a, b = st.columns([3, 1.4], vertical_alignment="center")
            with a:
                html(card_title("Document Health", "chart"))
            with b:
                html(f'<div style="text-align:right" class="la-sub">Health score '
                     f'<b style="color:#fff">{collection_score(docs)}%</b></div>')
            if not docs:
                html('<div class="la-empty">Upload a document to see its health here.</div>')
            else:
                total = c["total"]
                parts = [("Active", C["green"], c["active"]), ("Expiring Soon", C["amber"], c["expiring"]),
                         ("Critical", C["red"], c["critical"])]
                fig = pgo.Figure(pgo.Pie(
                    labels=[p[0] for p in parts], values=[p[2] for p in parts], hole=0.7, sort=False,
                    direction="clockwise", textinfo="none",
                    marker=dict(colors=[p[1] for p in parts], line=dict(color="#0F1534", width=3)),
                    hovertemplate="%{label}: %{value}<extra></extra>"))
                fig.update_layout(
                    showlegend=False, height=220, margin=dict(l=0, r=0, t=8, b=8),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    annotations=[dict(text=f"<b>{total}</b><br><span style='font-size:13px;color:#8B93B8'>Total</span>",
                                      showarrow=False, font=dict(size=28, color="#FFFFFF", family="Inter"))])
                d1, d2 = st.columns([1, 1.25], vertical_alignment="center")
                d1.plotly_chart(fig, config=PLOT_CFG, key="donut")
                with d2:
                    html(legend((lbl, col, n, round(100 * n / total)) for lbl, col, n in parts))

        with st.container(key="card_recent"):
            card_header("Recent Documents", "file", "Documents", key="recent")
            html(rows([row(file_badge(d.filename), d.filename, f"Uploaded on {fmt(uploaded_on(d))}",
                           pill_for(d)) for d in docs[:4]],
                      "No documents yet — upload your first one."))
            if not docs:
                st.button("Load demo documents", key="demo", on_click=load_demo)

    with right:
        with st.container(key="card_deadlines"):
            card_header("Upcoming Deadlines", "calendar", "Reminders", key="deadlines")
            ups = [d for d in upcoming(docs) if d.id not in completed][:5]
            html(rows([row(type_tile(d.doc_type, 38), friendly_title(d.filename), fmt(d.expiry_date),
                           pill_for(d)) for d in ups], "No upcoming deadlines."))

        if docs:
            with st.container(key="card_types"):
                html(card_title("Documents by Type", "list"))
                counts = pd.Series([d.doc_type for d in docs]).value_counts().sort_values()
                bar = pgo.Figure(pgo.Bar(
                    x=counts.values, y=counts.index, orientation="h", text=counts.values, textposition="outside",
                    marker=dict(color=[TYPE_STYLE.get(t, TYPE_STYLE["Other"])[1] for t in counts.index],
                                cornerradius=6),
                    hovertemplate="%{y}: %{x}<extra></extra>"))
                bar.update_layout(
                    height=max(150, 34 * len(counts) + 30), margin=dict(l=0, r=24, t=4, b=4),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", bargap=0.35,
                    font=dict(family="Inter", color="#AEB5D6", size=12),
                    xaxis=dict(visible=False), yaxis=dict(showgrid=False, ticksuffix="  "))
                st.plotly_chart(bar, config=PLOT_CFG, key="types")
        html(promo("Organize today,", "for a smoother", "tomorrow."))


def page_upload(docs: List[Document]) -> None:
    html(page_header("Upload Documents", "Add your important documents and let LifeAdmin handle the rest.", "upload"))
    saved: Dict[str, int] = st.session_state.setdefault("saved_uploads", {})
    cache: Dict[str, dict] = st.session_state.setdefault("analysis", {})
    filt = st.session_state.get("qfilter")
    exts = QUICK[filt][1] if filt else sorted(ALLOWED_EXTENSIONS)
    names = ", ".join(e.strip(".").upper() for e in exts if e != ".jpeg")
    st.markdown(f'<style>.st-key-card_drop{{--la-supports:"Supports {names} (Max {MAX_FILE_MB}MB)";}}</style>',
                unsafe_allow_html=True)

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
                    doc, text, conf = analyse_upload(data, f.name)
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
                    st.success(f"**{pick.name}** is saved to your vault.")
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
    html(page_header("Documents", "Search, filter, edit and manage everything you have stored.", "files"))
    if not docs:
        st.info("Your vault is empty. Go to **Upload** to add your first document.")
        return
    q = (st.session_state.get("q") or "").strip().lower()
    f1, f2 = st.columns([2.2, 1], vertical_alignment="bottom")
    with f1, st.container(key="doctabs"):
        status = st.segmented_control("Status", ["All", "Active", "Expiring Soon", "Critical", "Overdue", "No Expiry"],
                                      default="All", key="doc_status", label_visibility="collapsed") or "All"
    types = f2.multiselect("Type", DOC_TYPES, placeholder="All types", label_visibility="collapsed")
    level_of = {"Active": "active", "Expiring Soon": "warning", "Critical": "critical",
                "Overdue": "expired", "No Expiry": "none"}
    shown = [d for d in docs
             if (status == "All" or status_of(d).level == level_of[status])
             and (not types or d.doc_type in types)
             and (not q or q in haystack(d))]
    if q:
        st.caption(f'Filtered by search: "{q}"')

    df = documents_dataframe(shown)
    df["Status"] = [PILL[status_of(d).level][0] for d in shown]
    st.dataframe(df[["ID", "Type", "File", "Holder", "Number", "Organization", "Expiry", "Days left", "Status"]],
                 hide_index=True, width="stretch",
                 column_config={"Expiry": st.column_config.DateColumn(format="MMM DD, YYYY"),
                                "ID": st.column_config.NumberColumn(width="small")})
    if not shown:
        st.caption("No documents match these filters.")
        return

    ids = [d.id for d in shown]
    if st.session_state.get("doc_pick") not in ids:
        st.session_state.pop("doc_pick", None)
    by_id = {d.id: d for d in shown}
    pick = st.selectbox("Open document", ids, key="doc_pick",
                        format_func=lambda i: f"#{i} · {by_id[i].doc_type} · {by_id[i].filename}")
    doc = by_id[pick]

    left, right = st.columns([1.4, 1], gap="medium")
    with left, st.container(key="card_docinfo"):
        html(f'<div style="display:flex;gap:.8rem;align-items:center">{type_tile(doc.doc_type, 44)}'
             f'<div><div style="font-weight:700;color:#fff">{esc(friendly_title(doc.filename))}</div>'
             f'<div class="la-sub">{esc(doc.filename)} · uploaded {fmt(uploaded_on(doc))}</div></div></div>')
        html(fields_table(doc_fields(doc)))
        st.write("")
        html(status_block(doc))
        if doc.notes:
            st.caption(f"📝 {doc.notes}")
    with right, st.container(key="card_dochealth"):
        score = health_score(doc)
        html(card_title("Document Health", "chart"))
        html(health_meter(score, checks(doc), verdict(score)))
        html(f'<div class="la-sub" style="margin-top:.6rem">Timeliness: <b style="color:#fff">{timeliness_score(doc)}%</b>'
             f' · {"reminder completed" if doc.id in completed else esc(status_of(doc).message)}</div>')
        st.write("")
        if doc.stored_path and Path(doc.stored_path).exists():
            st.download_button("Download original", Path(doc.stored_path).read_bytes(), file_name=doc.filename,
                               icon=":material/download:", width="stretch", key=f"dl_{doc.id}")

    with st.expander("✏️ Edit details"):
        edited = doc_form(doc, f"edit_{doc.id}", "Update Document")
        if edited:
            db.update_document(edited)
            st.session_state["_toast"] = "Document updated"
            st.rerun()
    with st.popover("Delete document", icon=":material/delete:"):
        st.write(f"Permanently delete **{doc.filename}** and its stored file?")
        if st.button("Yes, delete", type="primary", key=f"del_{doc.id}"):
            db.delete_document(doc.id)
            st.session_state["_toast"] = "Document deleted"
            st.rerun()

    st.write("")
    with st.container(key="card_activity"):
        html(card_title("Activity History", "history"))
        logs = db.list_logs(100)
        if logs:
            log_df = pd.DataFrame([dict(r) for r in logs])[["created_at", "action", "detail"]]
            log_df.columns = ["When", "Action", "Detail"]
            log_df["When"] = log_df["When"].str.replace("T", "  ", regex=False)
            st.dataframe(log_df, hide_index=True, width="stretch", height=240)
        else:
            html('<div class="la-empty">No activity recorded yet.</div>')


def page_reminders(docs: List[Document], completed: set) -> None:
    html(page_header("Reminders & Deadlines", "Stay on top of your important dates and never miss a deadline.", "bell"))
    dated = [d for d in docs if d.expiry_date]
    up = [d for d in upcoming(docs) if d.id not in completed]
    od = [d for d in overdue(docs) if d.id not in completed]
    done = sorted((d for d in dated if d.id in completed), key=lambda d: d.expiry_date)

    left, right = st.columns([1.6, 1], gap="medium")
    with left:
        labels = {"All": "All", "Upcoming": f"Upcoming :blue-background[{len(up)}]",
                  "Overdue": f"Overdue :red-background[{len(od)}]", "Completed": "Completed"}
        with st.container(key="remtabs"):
            tab = st.segmented_control("Show", list(labels), format_func=labels.get, default="All",
                                       key="remtab_sel", label_visibility="collapsed") or "All"
        items = {"All": od + up, "Upcoming": up, "Overdue": od, "Completed": done}[tab]
        if not items:
            msg = {"Completed": "Nothing marked as completed yet.",
                   "Overdue": "Nothing overdue. 🎉"}.get(tab, "No deadlines to show. Add expiry dates to your documents.")
            html(f'<div class="la-empty" style="padding:2.5rem 0">{msg}</div>')
        for d in items:
            is_done = d.id in completed
            with st.container(key=f"rem_{d.id}"):
                a, b = st.columns([14, 1], vertical_alignment="center")
                with a:
                    html(f'<div class="la-rem">{type_tile(d.doc_type, 46)}<div style="flex:1;min-width:0">'
                         f'<div class="t">{esc(friendly_title(d.filename))}</div>'
                         f'<div class="d">{esc(reminder_text(d))}</div>'
                         f'<div class="w">{icon("calendar", 13)}<span>{fmt(d.expiry_date)}</span> {days_note(d)}</div></div>'
                         f'{pill_for(d, completed, upcoming_label=True)}</div>')
                with b, st.popover(":material/chevron_right:"):
                    st.markdown(f"**{esc(friendly_title(d.filename))}**")
                    if is_done:
                        st.button("Restore reminder", key=f"restore_{d.id}", width="stretch",
                                  on_click=user_action, args=(db.restore_reminder, d.id))
                    else:
                        st.button("Mark as completed", key=f"done_{d.id}", type="primary", width="stretch",
                                  on_click=user_action, args=(db.complete_reminder, d.id))
                    st.button("Open in Documents", key=f"open_{d.id}", width="stretch",
                              on_click=go, args=("Documents",), kwargs={"doc_pick": d.id, "doc_status": "All"})
                    st.download_button("Add to calendar (.ics)", to_ics([d]), f"lifeadmin_{d.id}.ics",
                                       "text/calendar", key=f"ics_{d.id}", width="stretch")

    with right:
        with st.container(key="card_calendar"):
            off = st.session_state.setdefault("cal_off", 0)
            y, m = divmod(TODAY.year * 12 + TODAY.month - 1 + off, 12)
            m += 1
            p, t, n = st.columns([1, 4, 1], vertical_alignment="center")
            with p, st.container(key="calnav_prev"):
                st.button("←", key="cal_prev", on_click=lambda: st.session_state.update(cal_off=off - 1))
            with t:
                html(f'<div class="la-cal-head">{date(y, m, 1):%B %Y}</div>')
            with n, st.container(key="calnav_next"):
                st.button("→", key="cal_next", on_click=lambda: st.session_state.update(cal_off=off + 1))
            colour = {"expired": C["red"], "critical": C["red"], "warning": C["amber"], "active": C["green"]}
            marks: Dict[date, list] = {}
            for d in dated:
                if d.id in completed:
                    continue
                marks.setdefault(d.expiry_date, []).append(
                    (colour.get(status_of(d).level, C["slate"]), friendly_title(d.filename)))
            html(month_calendar(y, m, marks, TODAY))

        with st.container(key="card_summary"):
            html(card_title("Quick Summary", "list"))
            this_month = sum(1 for d in dated if (d.expiry_date.year, d.expiry_date.month) == (TODAY.year, TODAY.month))
            html(summary_grid([("check", C["green"], len(up), "Upcoming"), ("alert", C["red"], len(od), "Overdue"),
                               ("list", C["blue"], len(dated), "Total Reminders"),
                               ("calendar", C["indigo"], this_month, "This Month")]))

        with st.container(key="card_export"):
            html(card_title("Export", "download"))
            e1, e2 = st.columns(2)
            e1.download_button("CSV", to_csv(docs), "lifeadmin_documents.csv", "text/csv",
                               icon=":material/table:", width="stretch", key="csv")
            e2.download_button("Calendar (.ics)", to_ics(docs), "lifeadmin_expiries.ics", "text/calendar",
                               icon=":material/event:", width="stretch", key="ics")
            st.caption("The .ics file adds every expiry to Google, Apple or Outlook Calendar with alerts 30 and 7 days before.")
        html(promo("Small steps today,", "big freedom tomorrow.", byline="LifeAdmin"))


def page_notes() -> None:
    st.title("Notes")
    st.caption("Your personal notes and lesson notes saved from PyLearn.")
    with st.form("new_note", clear_on_submit=True):
        title = st.text_input("Title", max_chars=200)
        content = st.text_area("Note", max_chars=20000)
        if st.form_submit_button("Save note", type="primary"):
            if not title.strip() or not content.strip():
                st.error("Enter a title and a note.")
            else:
                notes.create_note(user_id=signed_in_user["id"], source_app="lifeadmin",
                                  owner_id=str(signed_in_user["id"]), resource_id="personal",
                                  request_id=str(uuid4()), title=title.strip(), content=content.strip())
                st.success("Note saved.")
    if st.button("Refresh notes"):
        st.rerun()
    items = notes.list_notes(signed_in_user["id"], limit=100)
    if not items:
        st.info("No notes yet. Save a note from a PyLearn lesson to see it here.")
    for note in items:
        with st.container(border=True):
            st.subheader(note["title"])
            st.caption("PyLearn lesson" if note["source_app"] == "pylearn" else "Personal note")
            st.text(note["content"])
            st.caption(note["created_at"])
            if st.button("Delete note", key=f'delete_note_{note["id"]}'):
                notes.delete_note(note["id"], signed_in_user["id"])
                st.rerun()


# ================================================================ main
sidebar()
documents = db.list_documents()
done_ids = db.completed_ids()
user_name = db.get_user_name()
topbar(documents, done_ids, user_name)
if "_toast" in st.session_state:
    st.toast(st.session_state.pop("_toast"), icon="✅")

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
else:
    page_reminders(documents, done_ids)

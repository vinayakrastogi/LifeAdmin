"""Demo data: load the 24 sample documents so every screen has something to show.

Used by the "Load demo documents" button in the app and by scripts/load_demo.py.
Samples are regenerated relative to today (when reportlab is installed), run
through the real pipeline, stored, and a few get notes / a completed reminder.
"""
from __future__ import annotations

import importlib.util
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path

from . import database as db
from .pipeline import analyse_file, store_upload

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = ROOT / "sample_docs"


def _make_samples():
    spec = importlib.util.spec_from_file_location("make_samples", ROOT / "scripts" / "make_samples.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_demo(today: date | None = None, regenerate: bool = True) -> int:
    """Replace any earlier demo copies with fresh ones. Returns how many were loaded.

    Your own documents are never touched: only documents whose file name matches a
    sample are removed before reloading.
    """
    today = today or date.today()
    ms = _make_samples()
    if regenerate:
        try:
            ms.main(today, SAMPLE_DIR)
        except ImportError:   # reportlab / python-docx / openpyxl missing: use files on disk
            pass
    names = [n for n, _ in ms.samples(today)]
    paths = [SAMPLE_DIR / n for n in names if (SAMPLE_DIR / n).exists()]

    db.init_db()
    for doc in db.list_documents():
        if doc.filename in names:
            db.delete_document(doc.id)

    now = datetime.now()
    loaded = 0
    for i, p in enumerate(paths):
        doc, _, _ = analyse_file(p)
        doc.stored_path = store_upload(p.read_bytes(), p.name)
        # spread "uploaded on" dates over the last few weeks so lists look realistic
        doc.uploaded_at = (now - timedelta(days=(len(paths) - i) * 1.3)).isoformat(timespec="seconds")
        doc.notes = ms.NOTES.get(p.name, "")
        doc_id = db.add_document(doc)
        if p.name in ms.COMPLETED:
            db.complete_reminder(doc_id)
        loaded += 1
    db.log("DEMO", f"loaded {loaded} sample documents")
    return loaded


def reset_database() -> Path | None:
    """Back up the current database file and start empty. Returns the backup path."""
    if db.is_postgres():
        raise ValueError("Local reset is disabled when LIFEADMIN_DATABASE_URL is configured. Use a new empty cloud database.")
    if not db.DB_PATH.exists():
        return None
    backup = db.DB_PATH.with_name(f"lifeadmin_backup_{datetime.now():%Y%m%d_%H%M%S}.db")
    with closing(sqlite3.connect(db.DB_PATH)) as source, closing(sqlite3.connect(backup)) as target:
        source.backup(target)
    db.DB_PATH.unlink()
    for suffix in ("-wal", "-shm"):
        Path(str(db.DB_PATH) + suffix).unlink(missing_ok=True)
    db.set_current_user(None)
    db.init_db()
    return backup

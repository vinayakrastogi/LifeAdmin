"""Glue: file -> text -> classified, parsed Document (not yet saved)."""
from __future__ import annotations

import re
import tempfile
from uuid import uuid4
from pathlib import Path
from typing import Tuple

from . import database
from .classifier import classify
from .extractor import extract_text, validate_file
from .models import Document
from .parser import parse_document

UPLOAD_DIR = database.BASE_DIR / "data" / "uploads"


def analyse_text(text: str, filename: str = "") -> Tuple[Document, float]:
    doc_type, confidence = classify(text, filename)
    fields = parse_document(text)
    # A vehicle registration on an insurance policy is still an insurance document.
    return Document(filename=filename, doc_type=doc_type, **fields), confidence


def analyse_file(path: str | Path) -> Tuple[Document, str, float]:
    path = Path(path)
    text = extract_text(path)
    doc, confidence = analyse_text(text, path.name)
    return doc, text, confidence


def analyse_upload(data: bytes, filename: str) -> Tuple[Document, str, float]:
    """For web uploads: validate, write to a temp file, analyse."""
    validate_file(filename, len(data))
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / Path(filename).name
        p.write_bytes(data)
        return analyse_file(p)


def store_upload(data: bytes, filename: str) -> str:
    """Save the original file under data/uploads with a unique, safe name."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename).name)
    target = UPLOAD_DIR / f"{uuid4().hex}_{safe}"
    target.write_bytes(data)
    return str(target)

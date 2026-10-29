# 🗂️ LifeAdmin — Smart Personal Document & Deadline Manager

Upload a document → extract text → find key details → store in SQLite or PostgreSQL → dashboard → expiry alerts.

Hosted demo: [LifeAdmin](https://lifeadmin-aditya.onrender.com) ·
[API documentation](https://lifeadmin-api-aditya.onrender.com/docs).
The interface and API use separate free native Python services and share LifeAdmin's own
PostgreSQL database. See [DEPLOYMENT.md](DEPLOYMENT.md) for the exact configuration.
No paid AI or API keys needed; everything runs locally.

## Quick start

For the independent notes HTTP API and PyLearn / same-network setup, see
[API.md](API.md). It runs on port 8001 and keeps API callers separate from this
project's source and database.

The fixed internet endpoint is configured through ngrok. After setting up the
local environment, `python scripts/run_api.py` starts the API and tunnel together.
See [NGROK_SETUP.md](NGROK_SETUP.md) for startup and moving hosting to another device.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/make_samples.py   # optional: demo PDFs with dates relative to today
# Fresh install/reset only (backs up the previous database):
# python scripts/reset_database.py --confirm
streamlit run app.py
```

Sign in with `demostudent@example.com` / `demostudent` (student), or `demofaculty@example.com` / `demofaculty` (faculty) after the demo reset, or create
an account. Each user has private notes, documents, reminders and activity history.
Use the same email in PyLearn to see its lesson notes under **Notes**.

Open the **Upload** page and try the PDFs in `sample_docs/`, or press **Load demo documents** on an empty Dashboard.
Run the checks with `python -m pytest -q tests` and `python scripts/smoke_ui.py`.

## Demo data (24 sample documents)

Click **Load demo documents** (empty Dashboard, or the profile menu at the top right), or run:

```bash
python scripts/load_demo.py          # prompts for the demo account password
python scripts/load_demo.py --reset  # back up the database, start empty, then load
```

Dates are generated relative to today, so the demo always contains: 3 overdue (one already marked completed),
1 due today, 3 critical (1-7 days), 5 expiring soon (8-30 days), 9 active, 3 with no expiry
(Aadhaar, PAN, degree) and 1 incomplete scan with a low health score. Formats: PDF, Word, Excel and text.
Reloading replaces earlier demo copies and never touches your own documents.

## How it works (the 6 modules)

| # | Module | File | What it does |
|---|--------|------|--------------|
| 1 | Upload | `extractor.py::validate_file`, `pipeline.py` | Validates type/size (PDF, JPG, PNG, DOCX, XLSX, TXT · max 10 MB), saves original under `data/uploads/` |
| 2 | Text extraction | `extractor.py` | PDF text via `pypdf`, Word via `python-docx`, Excel via `openpyxl`; optional OCR for images/scans |
| 3 | Information extraction | `parser.py`, `classifier.py` | Regex finds dates, numbers, vehicle no., amount, name, organization; keyword scoring picks the type |
| 4 | Database | `database.py` | SQLite tables: `documents`, `reminders`, `users`, `activity_logs` |
| 5 | Dashboard | `app.py` | Totals, status donut, type bar, upcoming deadlines, recent documents (Plotly) |
| 6 | Smart reminders | `reminders.py` | >30 days Active · ≤30 Expiring soon · ≤7 Critical · past = Expired |

Extras: **Document Health score** (`health.py`, completeness + timeliness), CSV export and `.ics` calendar export with 30- and 7-day alarms (`export.py`), editable review form (extraction is never perfect), mark reminders completed/restore, activity log.

## Screens

The UI follows the screen designs in the project document (Figures 2-4). Styling lives in `lifeadmin/style.py` and `.streamlit/config.toml`.

| Screen | What's on it |
|--------|--------------|
| Dashboard | Greeting, 4 KPI cards (Total · Active · Expiring Soon · Critical), Document Health donut + health score, Recent Documents, Upcoming Deadlines, Documents by Type |
| Upload | Drag & drop zone (multiple files), Quick Upload type tiles, Review & Save form, Recent Uploads (Processed / Pending), Extracted Information with page thumbnail |
| Documents | Status tabs, type filter, table, details + health, edit, delete, activity history |
| Reminders | All / Upcoming / Overdue / Completed tabs, reminder cards, month calendar with deadline dots, Quick Summary, CSV/.ics export |

The top bar search filters documents from any page, the bell lists deadlines needing attention, and the avatar menu sets your name (stored in the `users` table).

## Notes

- Dates are read **day-first** (12/04/2026 = 12 April 2026).
- Extraction targets Indian formats (₹/Rs amounts, vehicle numbers like `TN 63 AB 1234`, PAN/Aadhaar patterns).
- Always review the pre-filled form before saving; you can correct any field.
- **OCR (optional):** install the Tesseract binary, then `pip install pytesseract Pillow` (add `pdf2image` + poppler for scanned PDFs).
- **ML (optional):** `classifier.train_ml_classifier(texts, labels)` trains a Naive Bayes model on your own labelled documents (needs `scikit-learn`).
- Locally, data lives in `data/` (SQLite file + uploaded originals). With `LIFEADMIN_DATABASE_URL`, records live in PostgreSQL while uploads still use the local filesystem. Use the documented reset script for local resets; do not delete files to reset a cloud database. The data directory is git-ignored.

## Project layout

```
app.py                 Streamlit UI (4 screens)
.streamlit/config.toml dark theme + 10 MB upload limit
lifeadmin/             models, database, extractor, parser, classifier, reminders, health, export, pipeline, preview, style
tests/                 pytest suite (29 tests)
scripts/               make_samples.py (24 demo docs), load_demo.py, smoke_ui.py (headless UI check)
sample_docs/           demo PDFs
data/                  created at runtime
```

## Ideas to extend

Email/WhatsApp reminders, multi-user login, a scikit-learn classifier trained on your data, renewal cost tracking, folder watching.
# Cloud database and deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) to share PostgreSQL between the Streamlit UI and API
using `LIFEADMIN_DATABASE_URL`. Leaving it blank retains local SQLite. Uploaded files remain temporary.

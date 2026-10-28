"""Load the 24 demo documents into LifeAdmin.

    python scripts/load_demo.py            # add/refresh the demo documents
    python scripts/load_demo.py --reset    # back up the database, start empty, then load

Dates are generated relative to today, so the demo always shows overdue,
due-today, critical, expiring-soon, active and no-expiry documents.
"""
import argparse
import sys
import getpass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lifeadmin.demo import load_demo, reset_database  # noqa: E402
from lifeadmin import auth, database
from lifeadmin.demo_accounts import seed_demo_accounts

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="back up the database and start empty first")
    ap.add_argument("--email", default="demostudent@example.com", help="Account receiving the sample documents")
    args = ap.parse_args()
    if args.reset:
        backup = reset_database()
        auth.init_auth()
        seed_demo_accounts()
        if backup:
            print(f"Backed up the old database to {backup}")
    auth.init_auth()
    try:
        token = auth.login(args.email, getpass.getpass("LifeAdmin password: "))
    except ValueError as exc:
        raise SystemExit(str(exc))
    database.set_current_user(auth.session_user(token)["id"])
    n = load_demo()
    print(f"Loaded {n} demo documents. Run: streamlit run app.py")

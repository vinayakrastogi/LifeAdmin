"""Explicit local reset with backup and the two demo logins; stop servers first."""
import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from lifeadmin import auth, database, notes
from lifeadmin.demo import reset_database
from lifeadmin.demo_accounts import seed_demo_accounts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", action="store_true", help="Reset database and create the two demo accounts.")
    args = parser.parse_args()
    if not args.confirm:
        parser.error("Stop LifeAdmin, then pass --confirm to reset its database.")
    backup = reset_database()
    auth.init_auth()
    notes.init_notes()
    seed_demo_accounts()
    print(f"Reset database: {database.DB_PATH}")
    if backup:
        print(f"Previous database backup: {backup}")
    print("Demo student: demostudent@example.com / demostudent")
    print("Demo faculty: demofaculty@example.com / demofaculty")
    print("No placeholder documents or notes were loaded.")


if __name__ == "__main__":
    main()

"""Copy an existing SQLite database to an EMPTY LIFEADMIN_DATABASE_URL.

Stop both local LifeAdmin processes before running this one-time command. The
SQLite source is opened read-only and is never reset or deleted.
"""
import argparse
from contextlib import closing
from pathlib import Path
import sqlite3
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from lifeadmin import auth, database as db, notes

TABLES = ("users", "documents", "reminders", "activity_logs", "sessions", "notes")
IDENTITY_TABLES = ("users", "documents", "reminders", "activity_logs")


def migrate(source_path: Path) -> dict[str, int]:
    if not db.is_postgres():
        raise ValueError("Configure LIFEADMIN_DATABASE_URL with the destination PostgreSQL URL.")
    if not source_path.is_file():
        raise ValueError("Source SQLite database does not exist.")
    auth.init_auth()
    notes.init_notes()
    counts = {}
    with closing(sqlite3.connect(source_path.resolve().as_uri() + "?mode=ro", uri=True)) as source:
        source.row_factory = sqlite3.Row
        with closing(db.connect()) as target, target:
            target.lock("schema")
            # Never merge unrelated users or silently overwrite an existing deployment.
            if any(target.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in TABLES):
                raise ValueError("Destination must be empty. Disable demo seeding before migrating.")
            source_tables = {row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for table in TABLES:
                counts[table] = 0
                if table not in source_tables:
                    continue
                allowed = target.columns(table)
                for row in source.execute(f"SELECT * FROM {table}"):
                    columns = list(row.keys())
                    if not set(columns) <= allowed:
                        raise ValueError(f"Unexpected source columns in {table}; update the local schema first.")
                    names = ", ".join(columns)
                    binds = ", ".join("?" for _ in columns)
                    target.execute(f"INSERT INTO {table} ({names}) VALUES ({binds})", tuple(row))
                    counts[table] += 1
            for table in IDENTITY_TABLES:
                maximum = target.execute(f"SELECT MAX(id) FROM {table}").fetchone()[0]
                if maximum is not None:
                    target.execute("SELECT setval(CAST(pg_get_serial_sequence(?, 'id') AS regclass), ?, true)",
                                   (table, maximum))
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=db.DB_PATH)
    args = parser.parse_args()
    counts = migrate(args.source)
    print("Migration completed; source SQLite database was preserved.")
    for table, count in counts.items():
        print(f"{table}: {count}")


if __name__ == "__main__":
    main()

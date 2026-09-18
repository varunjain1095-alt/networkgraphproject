"""Create empty SQLite database with full schema."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.env import load_env, project_root, resolve_path

SCHEMA_FILE = project_root() / "schema" / "schema.sql"
EXPECTED_TABLES = 25


def init_db(db_path: Path | None = None, force: bool = False) -> Path:
    load_env()
    target = db_path or resolve_path("DATABASE_PATH", "data/synthetic.db")
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        if not force:
            print(f"Database already exists: {target}")
            return target
        target.unlink()

    if not SCHEMA_FILE.is_file():
        raise FileNotFoundError(f"Schema file not found: {SCHEMA_FILE}")

    sql = SCHEMA_FILE.read_text(encoding="utf-8")
    with sqlite3.connect(target) as conn:
        conn.executescript(sql)
        tables = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchone()[0]

    if tables < EXPECTED_TABLES:
        raise RuntimeError(f"Expected at least {EXPECTED_TABLES} tables, found {tables}")

    print(f"Database initialized: {target} ({tables} tables)")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize empty SQLite schema")
    parser.add_argument("--force", action="store_true", help="Recreate database if it exists")
    parser.add_argument("--db", type=Path, default=None, help="Override database path")
    args = parser.parse_args()

    try:
        init_db(db_path=args.db, force=args.force)
        return 0
    except Exception as exc:
        print(f"init_db FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

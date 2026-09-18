"""Database connection helper for graph building."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from config.env import resolve_path


def open_db(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or resolve_path("DATABASE_PATH", "data/synthetic.db")
    if not path.is_file():
        raise FileNotFoundError(f"Database not found: {path}")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

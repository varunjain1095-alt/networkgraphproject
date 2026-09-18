"""SQLite helpers for bulk generation."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Sequence


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def executemany(conn: sqlite3.Connection, sql: str, rows: Iterable[Sequence]) -> None:
    conn.executemany(sql, list(rows))


def table_count(conn: sqlite3.Connection, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def clear_generated_data(conn: sqlite3.Connection) -> None:
    tables = [
        "influence_outcomes",
        "planted_influence_rules",
        "pairwise_connection_strength",
        "cluster_metrics",
        "node_metrics",
        "dataset_metadata",
        "trust_safety_events",
        "onboarding_events",
        "churn_events",
        "feature_exposure_log",
        "support_tickets",
        "community_participation",
        "source_recommendations",
        "source_follows",
        "contribution_validation_events",
        "contributions",
        "user_item_interactions",
        "activity_session_participants",
        "activity_sessions",
        "referrals",
        "relationship_edges",
        "trusted_sources",
        "items",
        "users",
        "organizations",
    ]
    conn.execute("PRAGMA foreign_keys = OFF")
    for table in tables:
        conn.execute(f"DELETE FROM {table}")
    conn.execute("PRAGMA foreign_keys = ON")

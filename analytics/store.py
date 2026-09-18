"""Persist computed metrics to SQLite and parquet."""

from __future__ import annotations

import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from config.env import resolve_path


def metrics_dir() -> Path:
    path = resolve_path("METRICS_DIR", "data/metrics")
    path.mkdir(parents=True, exist_ok=True)
    return path


def clear_metrics_tables(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM node_metrics")
    conn.execute("DELETE FROM cluster_metrics")
    conn.execute("DELETE FROM pairwise_connection_strength")


def save_node_metrics(conn: sqlite3.Connection, rows: list[tuple]) -> None:
    conn.executemany(
        """
        INSERT OR REPLACE INTO node_metrics
        (node_id, node_type, graph_layer, metric_name, metric_value, community_id, computed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def save_cluster_metrics(conn: sqlite3.Connection, rows: list[dict]) -> None:
    conn.executemany(
        """
        INSERT OR REPLACE INTO cluster_metrics
        (community_id, graph_layer, node_count, density, reciprocity, avg_exposure_rate, computed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                r["community_id"],
                r["graph_layer"],
                r["node_count"],
                r["density"],
                r["reciprocity"],
                r["avg_exposure_rate"],
                r["computed_at"],
            )
            for r in rows
        ],
    )


def save_pairwise(conn: sqlite3.Connection, rows: list[dict]) -> None:
    conn.executemany(
        """
        INSERT OR REPLACE INTO pairwise_connection_strength
        (user_id_a, user_id_b, relationship_strength, activity_strength, combined_strength, shared_experiment_ids)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (
                r["user_id_a"],
                r["user_id_b"],
                r["relationship_strength"],
                r["activity_strength"],
                r["combined_strength"],
                r["shared_experiment_ids"],
            )
            for r in rows
        ],
    )


def export_parquet(
    node_rows: list[tuple],
    cluster_rows: list[dict],
    pairwise_rows: list[dict],
) -> Path:
    out = metrics_dir()
    computed_at = datetime.now(timezone.utc).isoformat()

    node_df = pd.DataFrame(
        node_rows,
        columns=[
            "node_id",
            "node_type",
            "graph_layer",
            "metric_name",
            "metric_value",
            "community_id",
            "computed_at",
        ],
    )
    cluster_df = pd.DataFrame(cluster_rows)
    pairwise_df = pd.DataFrame(pairwise_rows)

    node_path = out / "node_metrics.parquet"
    cluster_path = out / "cluster_metrics.parquet"
    pairwise_path = out / "pairwise_connection_strength.parquet"
    meta_path = out / "metadata.json"

    node_df.to_parquet(node_path, index=False)
    cluster_df.to_parquet(cluster_path, index=False)
    pairwise_df.to_parquet(pairwise_path, index=False)
    meta_path.write_text(
        json.dumps({"computed_at": computed_at, "node_rows": len(node_df)}),
        encoding="utf-8",
    )
    return out

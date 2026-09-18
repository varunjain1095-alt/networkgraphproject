"""Safe PyG node feature allowlist (dataschema.md §13, BUG-1.07)."""

from __future__ import annotations

import sqlite3

import pandas as pd

ALLOWED_METRIC_NAMES = frozenset(
    {
        "degree",
        "betweenness",
        "eigenvector",
    }
)

NODE_TYPE_ENCODING = {"user": 0, "item": 1, "contribution": 2, "source": 3, "other": 4}


def load_metric_features(conn: sqlite3.Connection, graph_layer: str) -> pd.DataFrame:
    """Pivot precomputed node_metrics into a feature matrix (no _gen_* columns)."""
    metrics = pd.read_sql_query(
        """
        SELECT node_id, node_type, metric_name, metric_value, community_id
        FROM node_metrics
        WHERE graph_layer = ?
        """,
        conn,
        params=(graph_layer,),
    )
    if metrics.empty:
        return pd.DataFrame()

    pivot = metrics.pivot_table(
        index=["node_id", "node_type"],
        columns="metric_name",
        values="metric_value",
        aggfunc="first",
    )
    pivot = pivot.reset_index()
    safe_cols = [c for c in pivot.columns if c in ALLOWED_METRIC_NAMES or c in ("node_id", "node_type")]
    pivot = pivot[safe_cols]

    if "community_id" in metrics.columns:
        comm = metrics.drop_duplicates(subset=["node_id"]).set_index("node_id")["community_id"]
        pivot["community_id"] = pivot["node_id"].map(comm).fillna(-1)

    for name in ALLOWED_METRIC_NAMES:
        if name not in pivot.columns:
            pivot[name] = 0.0

    pivot["node_type_code"] = pivot["node_type"].map(lambda t: NODE_TYPE_ENCODING.get(t, NODE_TYPE_ENCODING["other"]))
    return pivot.fillna(0.0)


def feature_matrix_for_nodes(feature_df: pd.DataFrame, node_ids: list[str]) -> list[list[float]]:
    """Return feature rows aligned to node_ids order."""
    if feature_df.empty:
        return [[0.0, 0.0, 0.0, 0.0, 0.0] for _ in node_ids]

    lookup = feature_df.set_index("node_id")
    rows: list[list[float]] = []
    for node_id in node_ids:
        if node_id not in lookup.index:
            rows.append([0.0, 0.0, 0.0, 0.0, 0.0])
            continue
        row = lookup.loc[node_id]
        rows.append(
            [
                float(row.get("degree", 0.0)),
                float(row.get("betweenness", 0.0)),
                float(row.get("eigenvector", 0.0)),
                float(row.get("community_id", -1.0)),
                float(row.get("node_type_code", 0.0)),
            ]
        )
    return rows


FEATURE_NAMES = ("degree", "betweenness", "eigenvector", "community_id", "node_type_code")

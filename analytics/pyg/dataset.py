"""Build combined multi-layer PyG datasets (Phase 2.3)."""

from __future__ import annotations

import sqlite3

import pandas as pd

from analytics.pyg.convert import networkx_to_pyg, require_pyg
from analytics.pyg.features import load_metric_features
from analytics.utils import to_simple_graph
from graphs.cache import load_graph
from graphs.db import open_db


def _merge_user_layer_features(conn: sqlite3.Connection) -> pd.DataFrame:
    """Combine layer1, layer2, layer4 user metrics into one feature row per user."""
    frames = []
    for layer in ("layer1", "layer2", "layer4"):
        df = load_metric_features(conn, layer)
        if df.empty:
            continue
        users = df[df["node_type"] == "user"].copy()
        if users.empty:
            continue
        rename = {
            c: f"{layer}_{c}"
            for c in users.columns
            if c not in ("node_id", "node_type", "node_type_code")
        }
        users = users.rename(columns=rename)
        keep = ["node_id"] + [c for c in users.columns if c.startswith(layer)]
        frames.append(users[keep])

    if not frames:
        return pd.DataFrame()

    merged = frames[0]
    for frame in frames[1:]:
        merged = merged.merge(frame, on="node_id", how="outer")
    return merged.fillna(0.0)


def build_user_social_graph(conn: sqlite3.Connection | None = None):
    """Merged layer1 + layer2 user graph with combined metrics."""
    require_pyg()
    own = conn is None
    conn = conn or open_db()
    try:
        g1 = to_simple_graph(load_graph(1))
        g2 = to_simple_graph(load_graph(2))
        combined = g2.copy()
        for u, v, data in g1.edges(data=True):
            if combined.has_edge(u, v):
                w = combined[u][v].get("weight", 1.0) + data.get("weight", 1.0)
                combined[u][v]["weight"] = w
            else:
                combined.add_edge(u, v, **data)

        user_features = _merge_user_layer_features(conn)
        if not user_features.empty:
            feature_df = user_features.copy()
            feature_df["node_type"] = "user"
            feature_df["node_type_code"] = 0.0
            for col in ("degree", "betweenness", "eigenvector", "community_id"):
                parts = [c for c in feature_df.columns if c.endswith(f"_{col}")]
                if parts:
                    feature_df[col] = feature_df[parts].max(axis=1)
        else:
            feature_df = pd.DataFrame()

        data = networkx_to_pyg(combined, feature_df, layer="combined_social")
        data.graph_layer = "combined"
        return data, combined
    finally:
        if own:
            conn.close()


def build_adoption_graph(conn: sqlite3.Connection | None = None):
    """Layer 3 bipartite graph with enriched user features from L1/L2/L4."""
    require_pyg()
    own = conn is None
    conn = conn or open_db()
    try:
        graph = load_graph(3)
        user_extra = _merge_user_layer_features(conn)
        l3_features = load_metric_features(conn, "layer3")

        if not l3_features.empty and not user_extra.empty:
            users = l3_features[l3_features["node_type"] == "user"].set_index("node_id")
            for uid, row in user_extra.set_index("node_id").iterrows():
                if uid in users.index:
                    for col in row.index:
                        if col != "node_id":
                            users.loc[uid, col] = row[col]
                else:
                    users.loc[uid] = row
            items = l3_features[l3_features["node_type"] == "item"]
            features = pd.concat([users.reset_index(), items], ignore_index=True)
        else:
            features = l3_features

        data = networkx_to_pyg(graph, features, layer="layer3_adoption")
        return data, graph
    finally:
        if own:
            conn.close()


def load_adoption_labels(conn: sqlite3.Connection) -> pd.DataFrame:
    """All user–item interactions (organic + influenced)."""
    return pd.read_sql_query(
        "SELECT user_id, item_id, usage_total FROM user_item_interactions",
        conn,
    )


ADOPTION_INFLUENCE_RULES = ("rule_adoption", "rule_source")


def load_influenced_adoption_labels(conn: sqlite3.Connection) -> pd.DataFrame:
    """User–item pairs where the user received a planted adoption/source influence outcome.

    Aligns the combined adoption model with recoverable planted signal already in the DB
    (influence_outcomes × user_item_interactions) without regenerating Phase 1 data.
    """
    return pd.read_sql_query(
        """
        SELECT DISTINCT ui.user_id, ui.item_id, ui.usage_total
        FROM user_item_interactions ui
        INNER JOIN influence_outcomes io ON io.target_user_id = ui.user_id
        WHERE io.rule_id IN (?, ?)
        """,
        conn,
        params=ADOPTION_INFLUENCE_RULES,
    )


def load_churn_labels(conn: sqlite3.Connection) -> pd.DataFrame:
    """Historical churn flag (independent of graph — not used for GNN training)."""
    churned = pd.read_sql_query("SELECT user_id FROM churn_events", conn)
    active = pd.read_sql_query("SELECT user_id FROM users WHERE is_active = 1", conn)
    labels = pd.DataFrame({"user_id": active["user_id"].tolist() + churned["user_id"].tolist()})
    labels["churned"] = 0
    labels.loc[labels["user_id"].isin(churned["user_id"]), "churned"] = 1
    return labels.drop_duplicates(subset=["user_id"])


def load_cascade_risk_labels(
    conn: sqlite3.Connection,
    *,
    min_churned_neighbors: int = 2,
    positive_fraction: float = 0.25,
) -> pd.DataFrame:
    """Forward cascade exposure for active users on Layer 1.

    Counts direct churned neighbors per active user, then labels the top
    ``positive_fraction`` (at least ``min_churned_neighbors``) as cascade risk.
    Hop-based BFS labels collapse to all-ones on dense demo graphs.

    Derived from existing churn_events + relationship graph — no data regeneration.
    """
    graph = to_simple_graph(load_graph(1))
    churned = {
        row[0]
        for row in conn.execute("SELECT user_id FROM churn_events").fetchall()
    }
    active = {
        row[0]
        for row in conn.execute("SELECT user_id FROM users WHERE is_active = 1").fetchall()
    }

    counts: dict[str, int] = {}
    for user_id in active:
        if user_id not in graph:
            counts[user_id] = 0
            continue
        counts[user_id] = sum(1 for nbr in graph.neighbors(user_id) if str(nbr) in churned)

    if not counts:
        return pd.DataFrame(columns=["user_id", "cascade_risk", "churned_neighbor_count"])

    ordered_counts = sorted(counts.values())
    cutoff_idx = max(0, int(len(ordered_counts) * (1.0 - positive_fraction)) - 1)
    threshold = max(min_churned_neighbors, ordered_counts[cutoff_idx])

    user_ids = sorted(active)
    return pd.DataFrame(
        {
            "user_id": user_ids,
            "cascade_risk": [1 if counts[user_id] >= threshold else 0 for user_id in user_ids],
            "churned_neighbor_count": [counts[user_id] for user_id in user_ids],
        }
    )


def load_influence_edges(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(
        """
        SELECT source_user_id AS source, target_user_id AS target
        FROM influence_outcomes
        """,
        conn,
    )

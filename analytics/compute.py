"""Orchestrate all Phase 1C metric computation."""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timezone

import networkx as nx

from analytics.centrality import compute_layer_centralities, layer4_user_social_graph
from analytics.communities import compute_communities
from analytics.influence import compute_community_validated_influence, compute_pairwise_strength
from analytics.store import (
    clear_metrics_tables,
    export_parquet,
    save_cluster_metrics,
    save_node_metrics,
    save_pairwise,
)
from analytics.utils import iter_node_metric_rows, user_nodes
from graphs.cache import load_graph, load_projections
from graphs.db import open_db


def compute_all_metrics(seed: int = 42, db_path=None) -> dict:
    conn = open_db(db_path)
    computed_at = datetime.now(timezone.utc).isoformat()
    t0 = time.time()

    layer1 = load_graph(1)
    layer2 = load_graph(2)
    layer3 = load_graph(3)
    layer4 = load_graph(4)
    projections = load_projections()

    node_rows: list[tuple] = []
    cluster_rows: list[dict] = []

    print("Computing Layer 1 metrics...", flush=True)
    l1_central = compute_layer_centralities(layer1, "layer1", seed)
    l1_comm, l1_clusters = compute_communities(layer1, "layer1", seed)
    cluster_rows.extend(l1_clusters)
    for node, data in l1_central.items():
        node_rows.extend(
            iter_node_metric_rows(
                node,
                data["node_type"],
                "layer1",
                data["metrics"],
                l1_comm.get(node),
                computed_at,
            )
        )

    print("Computing Layer 2 metrics...", flush=True)
    l2_central = compute_layer_centralities(layer2, "layer2", seed)
    l2_comm, l2_clusters = compute_communities(layer2, "layer2", seed)
    cluster_rows.extend(l2_clusters)
    for node, data in l2_central.items():
        node_rows.extend(
            iter_node_metric_rows(
                node,
                data["node_type"],
                "layer2",
                data["metrics"],
                l2_comm.get(node),
                computed_at,
            )
        )

    print("Computing Layer 3 metrics...", flush=True)
    l3_central = compute_layer_centralities(layer3, "layer3", seed)
    l3_comm, l3_clusters = compute_communities(layer3, "layer3", seed)
    cluster_rows.extend(l3_clusters)
    for node, data in l3_central.items():
        node_rows.extend(
            iter_node_metric_rows(
                node,
                data["node_type"],
                "layer3",
                data["metrics"],
                l3_comm.get(node),
                computed_at,
            )
        )

    # Projection overlap scores on layer 3 user nodes
    user_proj = projections.get("user_user")
    if user_proj:
        proj_degree = dict(user_proj.degree(weight="shared_item_count"))
        for user_id in user_nodes(layer3):
            node_rows.append(
                (user_id, "user", "layer3", "taste_overlap_degree", float(proj_degree.get(user_id, 0)), l3_comm.get(user_id), computed_at)
            )

    print("Computing Layer 4 metrics...", flush=True)
    l4_social = layer4_user_social_graph(layer4)
    l4_central = compute_layer_centralities(l4_social, "layer4", seed)
    l4_comm, l4_clusters = compute_communities(l4_social, "layer4", seed)
    cluster_rows.extend(l4_clusters)
    for node, data in l4_central.items():
        node_rows.extend(
            iter_node_metric_rows(
                node,
                "user",
                "layer4",
                data["metrics"],
                l4_comm.get(node),
                computed_at,
            )
        )

    cvi = compute_community_validated_influence(conn, layer4, layer1)
    for user_id, score in cvi.items():
        node_rows.append(
            (user_id, "user", "layer4", "community_validated_influence", score, l4_comm.get(user_id), computed_at)
        )

    print("Computing pairwise connection strength...", flush=True)
    pairwise_rows = compute_pairwise_strength(conn, layer1, layer2)

    # Ensure every user has at least degree metric on layer1
    all_users = [r[0] for r in conn.execute("SELECT user_id FROM users")]
    covered = {r[0] for r in node_rows if r[2] == "layer1" and r[3] == "degree"}
    for user_id in all_users:
        if user_id not in covered:
            node_rows.append((user_id, "user", "layer1", "degree", 0.0, l1_comm.get(user_id), computed_at))

    print("Saving metrics...", flush=True)
    clear_metrics_tables(conn)
    save_node_metrics(conn, node_rows)
    save_cluster_metrics(conn, cluster_rows)
    save_pairwise(conn, pairwise_rows)
    conn.commit()
    export_parquet(node_rows, cluster_rows, pairwise_rows)
    conn.close()

    elapsed = round(time.time() - t0, 2)
    summary = {
        "node_metric_rows": len(node_rows),
        "cluster_rows": len(cluster_rows),
        "pairwise_rows": len(pairwise_rows),
        "communities_layer1": len(l1_clusters),
        "elapsed_seconds": elapsed,
    }
    _print_summary(summary)
    return summary


def _print_summary(meta: dict) -> None:
    print("\nMetrics summary:")
    print(f"  Node metric rows: {meta['node_metric_rows']:,}")
    print(f"  Cluster rows: {meta['cluster_rows']:,}")
    print(f"  Pairwise rows: {meta['pairwise_rows']:,}")
    print(f"  Layer 1 communities: {meta['communities_layer1']:,}")
    print(f"  Compute time: {meta['elapsed_seconds']}s")

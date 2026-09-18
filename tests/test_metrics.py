"""Phase 1C NetworkX metrics tests."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import networkx as nx
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_small_graph_degree_and_betweenness():
    sys.path.insert(0, str(ROOT))
    from analytics.centrality import compute_layer_centralities
    from analytics.utils import to_simple_graph

    g = nx.Graph()
    g.add_node("a", node_type="user")
    g.add_node("b", node_type="user")
    g.add_node("c", node_type="user")
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    results = compute_layer_centralities(g, "layer1", seed=1, betweenness_k=None)
    assert results["b"]["metrics"]["degree"] == 2.0
    assert results["b"]["metrics"]["betweenness"] > results["a"]["metrics"]["betweenness"]


def test_louvain_produces_multiple_communities():
    sys.path.insert(0, str(ROOT))
    from analytics.communities import compute_communities

    g = nx.karate_club_graph()
    for node in g.nodes():
        g.nodes[node]["node_type"] = "user"
    partition, clusters = compute_communities(g, "layer1", seed=42)
    assert len(clusters) >= 2
    assert len(partition) == g.number_of_nodes()


@pytest.fixture(scope="module")
def dev_metrics(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("metrics") / "test.db"
    graphs_dir = tmp_path_factory.mktemp("g") / "graphs"
    metrics_dir = tmp_path_factory.mktemp("m") / "metrics"
    env = {
        **__import__("os").environ,
        "DATABASE_PATH": str(db_path),
        "GRAPHS_DIR": str(graphs_dir),
        "METRICS_DIR": str(metrics_dir),
    }

    subprocess.run(
        [sys.executable, str(ROOT / "generator" / "run_generator.py"), "--scale", "dev", "--seed", "3", "--force-schema"],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [sys.executable, str(ROOT / "graphs" / "builder.py"), "--all-layers"],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [sys.executable, str(ROOT / "analytics" / "networkx_metrics.py")],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
    )
    return db_path, metrics_dir


def test_all_users_have_layer1_degree(dev_metrics):
    db_path, _ = dev_metrics
    conn = sqlite3.connect(db_path)
    missing = conn.execute(
        """
        SELECT COUNT(*) FROM users u
        LEFT JOIN node_metrics m
          ON u.user_id = m.node_id AND m.graph_layer = 'layer1' AND m.metric_name = 'degree'
        WHERE m.node_id IS NULL
        """
    ).fetchone()[0]
    conn.close()
    assert missing == 0


def test_no_zero_variance_betweenness(dev_metrics):
    db_path, _ = dev_metrics
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        """
        SELECT metric_value FROM node_metrics
        WHERE graph_layer = 'layer1' AND metric_name = 'betweenness'
        """
    ).fetchall()
    conn.close()
    values = [r[0] for r in rows]
    assert values
    assert max(values) > min(values)


def test_parquet_exports_exist(dev_metrics):
    _, metrics_dir = dev_metrics
    assert (metrics_dir / "node_metrics.parquet").is_file()
    assert (metrics_dir / "cluster_metrics.parquet").is_file()
    assert (metrics_dir / "pairwise_connection_strength.parquet").is_file()


def test_no_betweenness_in_dashboard():
    dashboard_dir = ROOT / "dashboard"
    if not dashboard_dir.exists():
        return
    for path in dashboard_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "betweenness_centrality" not in text

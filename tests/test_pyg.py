"""Phase 2 PyG conversion and split tests."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import networkx as nx
import pytest

ROOT = Path(__file__).resolve().parents[1]

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

pytestmark = [pytest.mark.integration, pytest.mark.pyg]


@pytest.fixture(scope="module")
def pyg_env(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("pyg") / "test.db"
    graphs_dir = tmp_path_factory.mktemp("g") / "graphs"
    metrics_dir = tmp_path_factory.mktemp("m") / "metrics"
    models_dir = tmp_path_factory.mktemp("md") / "models"
    env = {
        **__import__("os").environ,
        "DATABASE_PATH": str(db_path),
        "GRAPHS_DIR": str(graphs_dir),
        "METRICS_DIR": str(metrics_dir),
        "MODELS_DIR": str(models_dir),
    }
    for cmd in (
        [sys.executable, str(ROOT / "generator" / "run_generator.py"), "--scale", "dev", "--seed", "3", "--force-schema"],
        [sys.executable, str(ROOT / "graphs" / "builder.py"), "--all-layers"],
        [sys.executable, str(ROOT / "analytics" / "networkx_metrics.py")],
    ):
        subprocess.run(cmd, cwd=ROOT, env=env, check=True, capture_output=True)
    return env, models_dir


def test_networkx_to_pyg_shape():
    sys.path.insert(0, str(ROOT))
    from analytics.pyg.convert import networkx_to_pyg

    g = nx.karate_club_graph()
    mapping = {n: f"u{n}" for n in g.nodes()}
    g = nx.relabel_nodes(g, mapping)
    for n in g.nodes():
        g.nodes[n]["node_type"] = "user"
    nodes = list(g.nodes())
    data = networkx_to_pyg(g, __import__("pandas").DataFrame(), layer="layer1")
    assert data.x.shape[0] == len(nodes)
    assert data.edge_index.shape[0] == 2
    assert data.edge_index.shape[1] > 0


def test_export_all_layers(pyg_env):
    sys.path.insert(0, str(ROOT))
    import os

    env, models_dir = pyg_env
    os.environ.update(env)
    from analytics.pyg.convert import export_all_layers, load_pyg_layer

    out = export_all_layers(models_dir / "pyg")
    for layer in (1, 2, 3, 4):
        assert (out / f"layer{layer}.pt").is_file()
        data = load_pyg_layer(layer, out)
        assert data.num_nodes > 0
        assert data.x.shape[1] == 5


def test_feature_allowlist_excludes_gen_columns(pyg_env):
    sys.path.insert(0, str(ROOT))
    import os

    os.environ.update(pyg_env[0])
    from analytics.pyg.features import load_metric_features
    from graphs.db import open_db

    conn = open_db()
    try:
        df = load_metric_features(conn, "layer1")
    finally:
        conn.close()
    forbidden = {"activity_propensity", "quality_score", "popularity_score", "taste_cluster_id"}
    assert not forbidden.intersection(set(df.columns))


def test_community_split_reduces_leakage(pyg_env):
    sys.path.insert(0, str(ROOT))
    import os

    os.environ.update(pyg_env[0])
    from analytics.pyg.split import community_holdout_split, count_cross_split_edges, load_community_map
    from analytics.utils import to_simple_graph
    from graphs.cache import load_graph
    from graphs.db import open_db

    graph = to_simple_graph(load_graph(1))
    conn = open_db()
    try:
        comm_map = load_community_map(conn, "layer1")
    finally:
        conn.close()
    node_list = [str(n) for n in graph.nodes()]
    split = community_holdout_split(graph, comm_map, seed=1)
    assert split.train_mask.sum() > 0
    assert split.test_mask.sum() > 0
    cross = count_cross_split_edges(graph, split, node_list)
    assert cross >= 0


def test_audit_phase2_passes_on_exports(pyg_env):
    env, models_dir = pyg_env
    sys.path.insert(0, str(ROOT))
    import os

    os.environ.update(env)
    from analytics.pyg.convert import export_all_layers

    export_all_layers(models_dir / "pyg")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "audit_feature_columns.py"), "--phase2"],
        cwd=ROOT,
        env={**os.environ, "MODELS_DIR": str(models_dir)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr + result.stdout

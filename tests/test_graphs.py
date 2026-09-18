"""Phase 1B graph building tests."""

from __future__ import annotations

import pickle
import sqlite3
import subprocess
import sys
from pathlib import Path

import networkx as nx
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def dev_db_with_graphs(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("graphs") / "test.db"
    graphs_dir = tmp_path_factory.mktemp("g") / "graphs"
    env = {
        **__import__("os").environ,
        "DATABASE_PATH": str(db_path),
        "GRAPHS_DIR": str(graphs_dir),
    }

    gen = subprocess.run(
        [sys.executable, str(ROOT / "generator" / "run_generator.py"), "--scale", "dev", "--seed", "7", "--force-schema"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert gen.returncode == 0, gen.stderr

    build = subprocess.run(
        [sys.executable, str(ROOT / "graphs" / "builder.py"), "--all-layers"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr + build.stdout
    return db_path, graphs_dir


def test_all_layer_pickles_exist(dev_db_with_graphs):
    _, graphs_dir = dev_db_with_graphs
    for i in range(1, 5):
        assert (graphs_dir / f"layer{i}.gpickle").is_file()
    assert (graphs_dir / "projections.gpickle").is_file()


def test_layer1_user_count_matches_db(dev_db_with_graphs):
    db_path, graphs_dir = dev_db_with_graphs
    conn = sqlite3.connect(db_path)
    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()

    with (graphs_dir / "layer1.gpickle").open("rb") as handle:
        g = pickle.load(handle)
    user_nodes = [n for n, d in g.nodes(data=True) if d.get("node_type") == "user"]
    assert len(user_nodes) == user_count


def test_layer2_weights_vary(dev_db_with_graphs):
    _, graphs_dir = dev_db_with_graphs
    with (graphs_dir / "layer2.gpickle").open("rb") as handle:
        g: nx.Graph = pickle.load(handle)
    weights = [d.get("weight", 1) for _, _, d in g.edges(data=True)]
    assert weights
    assert max(weights) > min(weights)


def test_layer4_node_types(dev_db_with_graphs):
    _, graphs_dir = dev_db_with_graphs
    with (graphs_dir / "layer4.gpickle").open("rb") as handle:
        g = pickle.load(handle)
    types = {d.get("node_type") for _, d in g.nodes(data=True)}
    assert "user" in types
    assert "source" in types
    assert "contribution" in types


def test_ego_network_cap(dev_db_with_graphs):
    sys.path.insert(0, str(ROOT))
    from graphs.ego import extract_ego_network

    _, graphs_dir = dev_db_with_graphs
    with (graphs_dir / "layer1.gpickle").open("rb") as handle:
        g = pickle.load(handle)

    degrees = sorted(((n, g.degree(n)) for n in g.nodes()), key=lambda x: x[1], reverse=True)
    hub = degrees[0][0]
    ego, meta = extract_ego_network(g, hub, cap=50)
    assert ego.number_of_nodes() <= 50
    if meta["truncated"]:
        assert "Showing" in meta.get("message", "")


def test_cache_freshness_passes(dev_db_with_graphs):
    db_path, graphs_dir = dev_db_with_graphs
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_cache_freshness.py"), "--pre"],
        cwd=ROOT,
        env={
            **__import__("os").environ,
            "DATABASE_PATH": str(db_path),
            "GRAPHS_DIR": str(graphs_dir),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr

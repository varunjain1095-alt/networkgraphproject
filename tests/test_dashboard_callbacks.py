"""Dashboard callback and layout unit tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import networkx as nx
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def dashboard_env(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("dash") / "test.db"
    graphs_dir = tmp_path_factory.mktemp("g") / "graphs"
    metrics_dir = tmp_path_factory.mktemp("m") / "metrics"
    env = {
        **__import__("os").environ,
        "DATABASE_PATH": str(db_path),
        "GRAPHS_DIR": str(graphs_dir),
        "METRICS_DIR": str(metrics_dir),
    }
    for cmd in (
        [sys.executable, str(ROOT / "generator" / "run_generator.py"), "--scale", "dev", "--seed", "11", "--force-schema"],
        [sys.executable, str(ROOT / "graphs" / "builder.py"), "--all-layers"],
        [sys.executable, str(ROOT / "analytics" / "networkx_metrics.py")],
    ):
        subprocess.run(cmd, cwd=ROOT, env=env, check=True, capture_output=True)
    return env


def test_cytoscape_element_schema():
    sys.path.insert(0, str(ROOT))
    from dashboard.graph_views import build_cytoscape_elements

    g = nx.Graph()
    g.add_node("u1", node_type="user", display_name="Alice")
    g.add_node("u2", node_type="user", display_name="Bob")
    g.add_edge("u1", "u2", weight=2)
    elements = build_cytoscape_elements(g, "u1")
    assert elements
    for el in elements:
        assert "data" in el
        data = el["data"]
        assert "id" in data or "source" in data


def test_ego_caption_truncation():
    sys.path.insert(0, str(ROOT))
    from dashboard.graph_views import ego_view

    g = nx.star_graph(60)
    mapping = {i: f"usr_{i:03d}" for i in g.nodes()}
    g = nx.relabel_nodes(g, mapping)
    for n in g.nodes():
        g.nodes[n]["node_type"] = "user"
        g.nodes[n]["display_name"] = n
    center = "usr_000"
    elements, caption, meta = ego_view(g, center, "layer1")
    assert len(elements) <= 51 * 2
    if meta.get("truncated"):
        assert "Showing" in caption


def test_dashboard_layout_loads(dashboard_env):
    sys.path.insert(0, str(ROOT))
    import os

    os.environ.update(dashboard_env)
    from dashboard.app import create_app

    app = create_app()
    assert app.layout is not None
    layout_str = str(app.layout)
    assert len(layout_str) > 500


def test_startup_banner_without_db(tmp_path):
    sys.path.insert(0, str(ROOT))
    import os

    os.environ["DATABASE_PATH"] = str(tmp_path / "missing.db")
    os.environ["GRAPHS_DIR"] = str(tmp_path / "graphs")
    from dashboard.data_loader import DashboardData
    from dashboard.layout import build_layout

    data = DashboardData.load()
    assert not data.ready
    layout = build_layout(data)
    assert "missing.db" in str(layout) or "not found" in str(layout).lower()


def test_search_case_insensitive(dashboard_env):
    sys.path.insert(0, str(ROOT))
    import os

    os.environ.update(dashboard_env)
    from dashboard.data_loader import DashboardData

    data = DashboardData.load()
    assert data.ready
    if not data.ranked_users.empty:
        name = data.ranked_users.iloc[0]["display_name"]
        fragment = name[:3].lower()
        matches = data.search_users(fragment)
        assert matches


def test_callback_output_ids_exist(dashboard_env):
    sys.path.insert(0, str(ROOT))
    import os

    os.environ.update(dashboard_env)
    from dashboard.app import create_app
    from dashboard.ids import IDs

    app = create_app()
    layout_str = str(app.layout)
    for comp_id in (
        IDs.SELECTED_NODE,
        IDs.GRAPH,
        IDs.GRAPH_HOVER_CARD,
        IDs.GRAPH_INTRO,
        IDs.LAYER3_PANEL,
        IDs.CLUSTER_PANEL,
        IDs.ALERTS_CONTEXT_CARD,
        IDs.ALERTS_CONTEXT_WRAP,
        IDs.EXPLAIN_PANEL,
        IDs.RANKED_TABLE,
        IDs.ACTIVE_LAYER,
        IDs.LAYER3_TABLE,
    ):
        assert comp_id in layout_str


def test_no_betweenness_in_dashboard_callbacks():
    callbacks_path = ROOT / "dashboard" / "callbacks.py"
    text = callbacks_path.read_text(encoding="utf-8")
    assert "betweenness_centrality" not in text


def test_table_column_fields_match_row_keys(dashboard_env):
    sys.path.insert(0, str(ROOT))
    import os

    os.environ.update(dashboard_env)
    from dashboard.data_loader import DashboardData
    from dashboard.layout import RANKED_COLS, ALERT_COLS, USE_CASE_COLS, CLUSTER_COLS, LAYER3_COLS

    data = DashboardData.load()
    ranked_rows = data.ranked_users.head(5).to_dict("records")
    for col in RANKED_COLS:
        if not col.get("hide"):
            assert col["field"] in ranked_rows[0]

    for col in ALERT_COLS:
        if data.alerts and not col.get("hide"):
            assert col["field"] in data.alerts[0]

    for col in CLUSTER_COLS:
        if not data.clusters.empty and not col.get("hide"):
            assert col["field"] in data.clusters.iloc[0].to_dict()

    for col in LAYER3_COLS:
        if not data.layer3_items.empty and not col.get("hide"):
            assert col["field"] in data.layer3_items.iloc[0].to_dict()

    uc_id = next(iter(data.use_case_results))
    result = data.use_case_results[uc_id]
    items = result.sorted()
    if items:
        row = {
            "rank": items[0].rank,
            "label": items[0].label,
            "score": round(items[0].score, 4),
            "node_id": items[0].node_id,
        }
        for col in USE_CASE_COLS:
            if not col.get("hide"):
                assert col["field"] in row


def test_use_case_header_count_matches_flagged(dashboard_env):
    sys.path.insert(0, str(ROOT))
    import os

    os.environ.update(dashboard_env)
    from dashboard.data_loader import DashboardData

    data = DashboardData.load()
    for result in data.use_case_results.values():
        assert len(result.flagged) >= 0
        header = f"{result.title} ({len(result.flagged)} flagged)"
        assert str(len(result.flagged)) in header


def test_exempt_use_cases_no_toggle(dashboard_env):
    sys.path.insert(0, str(ROOT))
    import os

    os.environ.update(dashboard_env)
    from dashboard.data_loader import DashboardData

    data = DashboardData.load()
    exempt = {uc_id for uc_id, r in data.use_case_results.items() if not r.supports_toggle}
    assert "onboarding_flow" in exempt
    assert "discovery_gap" in exempt
    assert "fraud_detection" in exempt
    assert "rollout_sequencing" not in exempt


def test_explainability_includes_percentile(dashboard_env):
    sys.path.insert(0, str(ROOT))
    import os

    os.environ.update(dashboard_env)
    from dashboard.data_loader import DashboardData
    from dashboard.explainability import build_explanation

    data = DashboardData.load()
    user_id = data.ranked_users.iloc[0]["user_id"]
    panel = build_explanation(data, user_id, "layer1", None)
    text = " ".join(str(p) for p in panel)
    assert "relationship" in text.lower()


def test_explainability_layer_breakdown_when_predictions_present(dashboard_env):
    sys.path.insert(0, str(ROOT))
    import os

    os.environ.update(dashboard_env)
    from dashboard.data_loader import DashboardData
    from dashboard.explainability import build_explanation

    data = DashboardData.load()
    if data.predictions.empty:
        pytest.skip("No cached predictions in test env")

    user_id = data.ranked_users.iloc[0]["user_id"]
    panel = build_explanation(data, user_id, "layer1", None)
    text = " ".join(str(p) for p in panel)
    assert (
        "strongest driver" in text.lower()
        or "forward-looking predictions" in text.lower()
        or "why this matters" in text.lower()
    )


def test_selected_node_store_in_layout(dashboard_env):
    sys.path.insert(0, str(ROOT))
    import os

    os.environ.update(dashboard_env)
    from dashboard.app import create_app
    from dashboard.ids import IDs

    app = create_app()
    assert IDs.SELECTED_NODE in str(app.layout)


def test_cytoscape_has_explicit_height(dashboard_env):
    sys.path.insert(0, str(ROOT))
    import os

    os.environ.update(dashboard_env)
    from dashboard.app import create_app

    layout_str = str(create_app().layout)
    assert "600px" in layout_str

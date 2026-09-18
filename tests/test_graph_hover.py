"""Tests for ego graph hover card and layout tweaks."""

from __future__ import annotations

import sys
from pathlib import Path

import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.demo_profiles import get_demo_profile, load_demo_profiles, reload_demo_profiles
from dashboard.data_loader import DashboardData
from dashboard.graph_hover import HOVER_CARD_HIDDEN, HOVER_CARD_VISIBLE, build_hover_card
from dashboard.graph_views import build_cytoscape_elements, ego_view
from dashboard.layout import CYTOSCAPE_LAYOUT, CYTOSCAPE_STYLESHEET


def test_cytoscape_layout_has_spacing():
    assert CYTOSCAPE_LAYOUT["nodeRepulsion"] >= 8000
    assert CYTOSCAPE_LAYOUT["idealEdgeLength"] >= 80
    assert CYTOSCAPE_LAYOUT["nodeOverlap"] >= 20


def test_stylesheet_hides_labels_until_selected():
    base = next(s for s in CYTOSCAPE_STYLESHEET if s["selector"] == "node")
    selected = next(s for s in CYTOSCAPE_STYLESHEET if s["selector"] == "node:selected")
    center = next(s for s in CYTOSCAPE_STYLESHEET if s["selector"] == "node.center")
    assert "label" not in base["style"]
    assert selected["style"].get("label") == "data(label)"
    assert center["style"]["background-color"] == "#22c55e"


def test_build_cytoscape_elements_includes_stats():
    g = nx.Graph()
    g.add_node("u1", node_type="user", display_name="Alice")
    stats = {
        "u1": {
            "rank": 3,
            "score": 0.42,
            "percentile": "top 1%",
            "layer1_degree": 12.0,
        }
    }
    elements = build_cytoscape_elements(g, "u1", user_stats=stats)
    node = next(el for el in elements if el["data"].get("id") == "u1")
    assert node["data"]["rank"] == 3
    assert node["data"]["score"] == 0.42
    assert node["data"]["is_center"] is True
    assert "center" in node["classes"]


def test_hover_card_renders_demo_profile():
    data = DashboardData(db_path=Path("missing.db"))
    card = build_hover_card(
        data,
        {"id": "usr_00347", "node_type": "user", "is_center": True},
    )
    text = " ".join(str(part) for part in card)
    assert "Priya Sharma" in text
    assert "Female" in text
    assert "Bangalore" in text
    assert "March 2022" in text
    assert "Ego center" in text
    assert "Rank" not in text
    assert "Influence score" not in text


def test_hover_card_fallback_without_demo_profile():
    data = DashboardData(db_path=Path("missing.db"))
    data.users_lookup = {"usr_99999": {"display_name": "User 99999"}}
    card = build_hover_card(data, {"id": "usr_99999", "node_type": "user"})
    text = " ".join(str(part) for part in card)
    assert "User 99999" in text
    assert "usr_99999" in text
    assert "Demo profile not set" in text


def test_ego_view_caption_mentions_hover():
    g = nx.star_graph(5)
    mapping = {i: f"u{i}" for i in g.nodes()}
    g = nx.relabel_nodes(g, mapping)
    for n in g.nodes():
        g.nodes[n]["node_type"] = "user"
        g.nodes[n]["display_name"] = n
    _, caption, _ = ego_view(g, "u0", "layer1")
    assert "Hover" in caption


def test_demo_profiles_load_placeholders():
    reload_demo_profiles()
    profile = get_demo_profile("usr_00158")
    assert profile is not None
    assert profile.name == "Marcus Chen"
    assert profile.location == "Singapore"


def test_hover_card_styles():
    assert HOVER_CARD_VISIBLE["display"] == "block"
    assert HOVER_CARD_HIDDEN["display"] == "none"

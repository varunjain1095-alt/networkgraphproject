"""Tests for alerts context card, cluster view, and layer4 graph fixes."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.alert_context import build_alerts_context_card
from dashboard.cluster_view import build_cluster_bubble_panel, cluster_explainability
from dashboard.graph_views import ego_view
from dashboard.layer_copy import layer_graph_intro
from use_cases.base import FlaggedItem, UseCaseResult


def test_layer4_intro_matches_actual_stylesheet_colors():
    intro = layer_graph_intro("layer4")
    assert "green is the selected user" in intro.lower()
    assert "blue nodes are other people" in intro.lower()
    assert "orange are trusted sources" in intro.lower()
    assert "purple are contributions" in intro.lower()


def test_layer4_ego_includes_other_users():
    from graphs.cache import load_graph

    graphs_dir = ROOT / "data" / "graphs"
    if not (graphs_dir / "layer4.gpickle").exists():
        import pytest

        pytest.skip("layer4 graph not on disk")

    g = load_graph(4)
    center = next(n for n, d in g.nodes(data=True) if d.get("node_type") == "user")
    elements, _caption, _meta = ego_view(g, center, "layer4")
    node_types = {el["data"].get("node_type") for el in elements if "source" not in el.get("data", {})}
    assert "user" in node_types
    assert "source" in node_types
    assert "contribution" in node_types
    user_nodes = [el for el in elements if el.get("data", {}).get("node_type") == "user"]
    assert len(user_nodes) > 1


def test_layer4_non_center_users_have_user_class_not_only_center():
    from graphs.cache import load_graph

    graphs_dir = ROOT / "data" / "graphs"
    if not (graphs_dir / "layer4.gpickle").exists():
        import pytest

        pytest.skip("layer4 graph not on disk")

    g = load_graph(4)
    center = next(n for n, d in g.nodes(data=True) if d.get("node_type") == "user")
    elements, _, _ = ego_view(g, center, "layer4")
    other_users = [
        el
        for el in elements
        if el.get("data", {}).get("node_type") == "user" and el["data"]["id"] != center
    ]
    assert other_users
    assert all("user" in el.get("classes", "") for el in other_users)
    assert all("center" not in el.get("classes", "") for el in other_users)


def test_alerts_context_card_shows_user_specific_flags():
    item = FlaggedItem(
        node_id="usr_001",
        explanation="Alice has no active connections. Recommend guided onboarding with buddy matching.",
        recommended_action="Assign guided onboarding.",
    )
    result = UseCaseResult(
        use_case_id="onboarding_flow",
        title="Onboarding flow decisioning",
        flagged=[item],
    )

    class FakeData:
        use_case_results = {"onboarding_flow": result}

        def user_display(self, user_id):
            return "Alice"

        def flags_for_user(self, user_id):
            return [("onboarding_flow", result.title, item)]

    card = build_alerts_context_card(FakeData(), "usr_001")
    rendered = str(card)
    assert "Onboarding flow decisioning" in rendered
    assert "no active connections" in rendered.lower()
    assert "onboarding path affects early retention" in rendered.lower()


def test_alerts_context_card_condenses_repeated_use_case():
    items = [
        (
            "ab_contamination",
            "A/B test contamination detection",
            FlaggedItem(
                node_id=f"usr_001|usr_{i:03d}",
                explanation=f"Pair {i} detail text.",
                metrics={"combined_strength": 0.76 + i * 0.01},
                extra={"user_id_b": f"usr_{i:03d}"},
            ),
        )
        for i in range(5)
    ]

    class FakeData:
        def user_display(self, user_id):
            return "Alice"

        def flags_for_user(self, user_id):
            return items

    rendered = str(build_alerts_context_card(FakeData(), "usr_001"))
    assert "Flagged in 1 use case (5 total signals)" in rendered
    assert "Show 5 individual instances" in rendered
    assert "connected to 5 other users" in rendered


def test_alerts_context_card_lists_multiple_use_cases():
    items = [
        ("onboarding_flow", "Onboarding flow decisioning", FlaggedItem(node_id="usr_001", explanation="one")),
        ("rollout_sequencing", "Feature rollout sequencing", FlaggedItem(node_id="usr_001", explanation="two")),
    ]

    class FakeData:
        def user_display(self, user_id):
            return "Alice"

        def flags_for_user(self, user_id):
            return items

    rendered = str(build_alerts_context_card(FakeData(), "usr_001"))
    assert "Flagged in 2 use cases" in rendered
    assert "Onboarding flow decisioning" in rendered
    assert "Feature rollout sequencing" in rendered


def test_cluster_bubble_panel_not_empty():
    class FakeData:
        clusters = pd.DataFrame(
            {"community_id": [1, 2], "node_count": [89, 18], "density": [0.55, 0.22]}
        )

    panel = build_cluster_bubble_panel(FakeData(), selected_cluster_id=1)
    assert "89 users" in str(panel)


def test_cluster_explainability_uses_cluster_stats():
    class FakeData:
        clusters = pd.DataFrame({"community_id": [5], "node_count": [89], "density": [0.55]})

    panel = cluster_explainability(FakeData(), 5)
    assert "89" in str(panel)

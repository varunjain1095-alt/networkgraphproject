"""Tests for layer-specific dashboard copy and panels."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.layer_copy import layer_graph_intro, layer_user_summary, layer_why_this_matters
from dashboard.layer_panels import build_coownership_grid, build_ownership_intro


def test_layer_graph_intros_differ_by_layer():
    layer1 = layer_graph_intro("layer1")
    layer2 = layer_graph_intro("layer2")
    layer3 = layer_graph_intro("layer3")
    layer4 = layer_graph_intro("layer4")
    assert layer1 != layer2
    assert "co-play" in layer2.lower() or "shared activity" in layer2.lower()
    assert "rankings" in layer3.lower() or "table" in layer3.lower()
    assert "curator" in layer4.lower() or "trust" in layer4.lower()
    assert "green is the selected user" in layer4.lower()
    assert "blue nodes are other people" in layer4.lower()
    assert "orange are trusted sources" in layer4.lower()
    for text in (layer1, layer2, layer3, layer4):
        assert "\u2014" not in text
        assert "\u2013" not in text


def test_layer_user_summary_is_layer_specific():
    row = pd.Series(
        {
            "layer1_degree": 12.0,
            "layer1_betweenness": 0.02,
            "layer2_degree": 8.0,
            "layer2_community_id": 3,
            "layer3_degree": 5.0,
            "layer4_degree": 4.0,
            "layer4_eigenvector": 0.08,
        }
    )
    rel = layer_user_summary("Alice", "layer1", row)
    activity = layer_user_summary("Alice", "layer2", row)
    ownership = layer_user_summary("Alice", "layer3", row)
    reviews = layer_user_summary("Alice", "layer4", row)
    assert rel != activity != ownership != reviews
    assert "relationship" in rel.lower()
    assert "shared activity" in activity.lower() or "co-participates" in activity.lower()
    assert "ownership" in ownership.lower()
    assert "curator" in reviews.lower() or "trust" in reviews.lower()


def test_layer_why_this_matters_varies():
    assert layer_why_this_matters("Alice", "layer1") != layer_why_this_matters("Alice", "layer3")


def test_ownership_intro_is_never_empty():
    class FakeData:
        def layer3_for_user(self, _user_id):
            return []

        def user_display(self, user_id):
            return user_id

    intro = build_ownership_intro(FakeData(), None)
    rendered = str(intro)
    assert "Ownership patterns" in rendered
    assert len(rendered) > 40


def test_coownership_grid_renders_cells():
    class FakeData:
        layer3_items = pd.DataFrame(
            {
                "display_name": ["A", "A", "B", "B", "C"],
                "item": ["Game 1", "Game 2", "Game 1", "Game 2", "Game 1"],
                "interaction_type": ["play"] * 5,
                "usage_total": [10, 8, 9, 7, 5],
            }
        )

        def user_display(self, user_id):
            return user_id

        def layer3_for_user(self, user_id):
            return self.layer3_items[self.layer3_items["display_name"] == user_id].to_dict("records")

    grid = build_coownership_grid(FakeData(), "A")
    rendered = str(grid)
    assert "Items frequently owned together" in rendered

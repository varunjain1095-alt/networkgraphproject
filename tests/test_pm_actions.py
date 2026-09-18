"""Tests for PM actions and cluster hover."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.cluster_hover import build_cluster_hover_card
from dashboard.data_loader import DashboardData
from dashboard.pm_actions import (
    build_exclude_list_panel,
    build_exclude_panel_content,
    pm_actions_section,
    success_message,
)
from use_cases.base import FlaggedItem, UseCaseResult


def test_pm_actions_section_has_two_buttons_and_no_disclaimer():
    section = pm_actions_section("ranked", "Alice")
    rendered = str(section)
    assert "Recommend item" in rendered
    assert "Forward to marketing" in rendered
    assert "ranked" in rendered
    assert "illustrative" not in rendered.lower()
    assert "nothing is sent" not in rendered.lower()


def test_exclude_list_panel_remove_buttons():
    entries = [
        {
            "user_id": "usr_001",
            "display_name": "Alice",
            "tests": ["A/B test 1"],
            "main_user_id": "usr_100",
            "strength": 0.82,
        }
    ]
    panel = build_exclude_list_panel(entries)
    rendered = str(panel)
    assert "usr_001" in rendered
    assert "A/B test 1" in rendered
    assert "Remove" in rendered


def test_exclude_panel_shows_connections_and_tests():
    content = build_exclude_panel_content(
        "usr_100",
        "Alice",
        [
            {"user_id": "usr_001", "display_name": "Bob", "strength": 0.76},
            {"user_id": "usr_002", "display_name": "Carol", "strength": 0.61},
        ],
        ["A/B test 1", "A/B test 2"],
    )
    rendered = str(content)
    assert "pm-exclude-tests" in rendered
    assert "pm-exclude-connections" in rendered
    assert "strength 0.76" in rendered
    assert "A/B test 1" in rendered
    assert "Confirm exclusions" in rendered


def test_success_message_styling():
    msg = success_message("Items recommended to user's network.")
    rendered = str(msg)
    assert "Items recommended" in rendered
    assert "#15803d" in rendered


def test_ab_contamination_connections_from_flags():
    items = [
        FlaggedItem(
            node_id="usr_100|usr_001",
            metrics={"combined_strength": 0.76},
            extra={"user_id_b": "usr_001", "experiments": ["exp_alpha", "exp_beta"]},
        ),
        FlaggedItem(
            node_id="usr_100|usr_002",
            metrics={"combined_strength": 0.61},
            extra={"user_id_b": "usr_002", "experiments": ["exp_alpha"]},
        ),
    ]
    result = UseCaseResult(
        use_case_id="ab_contamination",
        title="A/B test contamination detection",
        flagged=items,
    )

    class FakeData:
        use_case_results = {"ab_contamination": result}

        def user_display(self, user_id):
            return {"usr_100": "Alice", "usr_001": "Bob", "usr_002": "Carol"}.get(user_id, user_id)

    data = FakeData()
    connections, tests = DashboardData.ab_contamination_connections(data, "usr_100")
    assert len(connections) == 2
    assert connections[0]["user_id"] == "usr_001"
    assert connections[0]["strength"] == 0.76
    assert "exp_alpha" in tests
    assert "exp_beta" in tests


def test_cluster_hover_card_caps_members():
    class FakeData:
        def cluster_members(self, community_id, limit=15):
            return [f"usr_{i:03d}" for i in range(limit)], 89

    children, style = build_cluster_hover_card(FakeData(), 3)
    rendered = str(children)
    assert "Community 3" in rendered
    assert "89 users" in rendered
    assert "Showing 15 of 89" in rendered
    assert style.get("display") == "block"

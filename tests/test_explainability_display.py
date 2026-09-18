"""Tests for plain-language explainability display helpers."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.explainability_display import (
    format_layer_breakdown_plain,
    group_related_flags,
    influence_sentence,
    item_involves_user,
    prediction_plain_summary,
    summarize_use_case_flags,
)
from use_cases.base import FlaggedItem, UseCaseResult


def test_influence_sentence_uses_plain_language():
    text = influence_sentence("Alice", 2, 500, "top 1%")
    assert "Alice" in text
    assert "influential" in text
    assert "eigenvector" not in text


def test_prediction_plain_summary_hides_raw_percentages_by_default():
    text = prediction_plain_summary("adoption", 0.62, 0.29, "itm_0001")
    assert "moderate signal" in text
    assert "lower confidence" in text
    assert "29%" not in text
    assert "62%" not in text


def test_layer_breakdown_plain_names():
    contributions = [
        ("Layer 2 — Shared activity", 0.5),
        ("Layer 1 — Relationships", 0.3),
        ("Layer 3 — User–item", 0.2),
    ]
    lead, lines, details = format_layer_breakdown_plain(contributions)
    assert "Shared activity" in lead
    assert "Relationships" in lines[1]
    assert "Ownership patterns" in lines[2]
    assert "Layer 1" not in lead
    assert "50%" in details


def test_ab_contamination_flags_condense():
    items = [
        FlaggedItem(
            node_id=f"usr_001|usr_{i:03d}",
            explanation=f"Pair {i} explanation with enough detail to verify no truncation.",
            metrics={"combined_strength": 0.76 + i * 0.01},
            extra={"user_id_b": f"usr_{i:03d}"},
        )
        for i in range(4)
    ]
    summary, details = summarize_use_case_flags("A/B test contamination detection", items, "usr_001")
    assert "connected to 4 other users" in summary
    assert "0.76" in summary and "0.79" in summary
    assert len(details) == 4
    assert all("verify no truncation." in d for d in details)


def test_group_related_flags_by_use_case():
    result = UseCaseResult(
        use_case_id="ab_contamination",
        title="A/B test contamination detection",
        flagged=[
            FlaggedItem(node_id="usr_001|usr_002", explanation="one", extra={"user_id_b": "usr_002"}),
            FlaggedItem(node_id="usr_001|usr_003", explanation="two", extra={"user_id_b": "usr_003"}),
        ],
    )
    grouped = group_related_flags({"ab_contamination": result}, "usr_001")
    assert len(grouped["A/B test contamination detection"]) == 2


def test_item_involves_user_for_pair_ids():
    item = FlaggedItem(node_id="usr_001|usr_002", explanation="pair")
    assert item_involves_user(item, "usr_002")


def test_no_em_or_en_dash_in_generated_panel_text():
    samples = [
        influence_sentence("Alice", 2, 500, "top 1%"),
        prediction_plain_summary("adoption", 0.62, 0.29, "itm_0001"),
    ]
    lead, lines, details = format_layer_breakdown_plain(
        [
            ("Layer 2 — Shared activity", 0.5),
            ("Layer 1 — Relationships", 0.3),
        ]
    )
    samples.extend([lead, *lines, details])
    for text in samples:
        assert "\u2014" not in text
        assert "\u2013" not in text


def test_sanitize_display_text_replaces_legacy_dashes():
    from dashboard.explainability_display import sanitize_display_text

    cleaned = sanitize_display_text("Foo — bar continues here")
    assert "\u2014" not in cleaned
    assert "Foo" in cleaned


def test_details_block_includes_score_content():
    from dashboard.explainability import _details_block

    block = _details_block("Show exact prediction scores", ["Adoption: score 62%, confidence 29%"])
    rendered = str(block)
    assert "62%" in rendered
    assert "29%" in rendered


def test_details_block_hidden_when_empty():
    from dashboard.explainability import _details_block

    assert _details_block("Show exact layer percentages", []) is None


def test_related_flag_expand_includes_individual_explanations():
    from dashboard.explainability_display import related_flag_blocks

    items = [
        FlaggedItem(
            node_id=f"usr_001|usr_{i:03d}",
            explanation=f"Full explanation number {i}.",
            extra={"user_id_b": f"usr_{i:03d}"},
        )
        for i in range(3)
    ]
    grouped = {"A/B test contamination detection": items}
    blocks = related_flag_blocks(grouped, "usr_001")
    rendered = str(blocks)
    assert "Full explanation number 0." in rendered
    assert "Full explanation number 2." in rendered
    assert "connected to 3 other users" in rendered

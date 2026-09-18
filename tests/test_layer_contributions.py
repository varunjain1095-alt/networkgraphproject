"""Tests for per-layer contribution breakdown (Phase 2 explainability)."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.layer_contributions import compute_layer_contributions, format_contribution_breakdown


def test_contributions_normalize_to_one():
    row = pd.Series(
        {
            "layer1_eigenvector": 0.8,
            "layer2_degree": 25.0,
            "layer3_degree": 10.0,
            "layer4_eigenvector": 0.2,
        }
    )
    preds = pd.DataFrame(
        {
            "user_id": ["u1"],
            "prediction_type": ["adoption"],
            "score": [0.6],
            "confidence": [0.7],
            "target_id": ["item1"],
        }
    )
    contributions = compute_layer_contributions(row, preds, "u1")
    assert len(contributions) == 4
    assert abs(sum(share for _, share in contributions) - 1.0) < 1e-6
    assert contributions[0][0] == "Layer 1 — Relationships"


def test_contributions_fallback_equal_weights():
    row = pd.Series({"user_id": "u1"})
    contributions = compute_layer_contributions(row, pd.DataFrame(), "u1")
    assert all(abs(share - 0.25) < 1e-6 for _, share in contributions)


def test_format_contribution_breakdown():
    text = format_contribution_breakdown([("Layer 1 — Relationships", 0.5), ("Layer 2 — Shared activity", 0.3)])
    assert "Layer 1" in text
    assert "50%" in text
    assert "30%" in text


def test_format_contribution_breakdown_empty():
    assert "Insufficient" in format_contribution_breakdown([])

"""Unit tests for link-prediction eval helpers (no full training run)."""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

torch = pytest.importorskip("torch")

from analytics.pyg.train import _build_balanced_test_pairs, _link_eval_metrics, _mask_edge_index


def test_link_eval_metrics_balanced_baseline_is_half():
    logits = torch.tensor([2.0, 2.0, -2.0, -2.0])
    labels = torch.tensor([1.0, 1.0, 0.0, 0.0])
    accuracy, baseline, recovery = _link_eval_metrics(logits, labels)
    assert accuracy == 1.0
    assert baseline == 0.5
    assert recovery == 0.5


def test_link_eval_metrics_all_positive_labels_baseline_one():
    logits = torch.tensor([2.0, 2.0])
    labels = torch.tensor([1.0, 1.0])
    _, baseline, _ = _link_eval_metrics(logits, labels)
    assert baseline == 1.0


def test_build_balanced_test_pairs_includes_negatives():
    pos = [("u1", "i1"), ("u2", "i2"), ("u3", "i3")]
    pos_set = set(pos)
    rng = random.Random(0)
    pairs = _build_balanced_test_pairs(
        pos, {"u1", "u2"}, ["i1", "i2", "i3", "i4"], pos_set, rng, endpoint="first"
    )
    assert pairs
    assert any(label == 1 for *_, label in pairs)
    assert any(label == 0 for *_, label in pairs)
    assert len([p for p in pairs if p[2] == 1]) == len([p for p in pairs if p[2] == 0])


def test_link_eval_metrics_imbalanced_baseline():
    logits = torch.tensor([2.0, -2.0, -2.0, -2.0])
    labels = torch.tensor([1.0, 0.0, 0.0, 0.0])
    _, baseline, _ = _link_eval_metrics(logits, labels)
    assert baseline == 0.75


def test_mask_edge_index_removes_holdout():
    edge_index = torch.tensor([[0, 1, 2], [1, 2, 0]], dtype=torch.long)
    masked = _mask_edge_index(edge_index, ["a", "b", "c"], {("a", "b")})
    assert masked.shape[1] < edge_index.shape[1]

"""Training stability helpers and smoke checks."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from analytics.pyg.train import TrainConfig, _prepare_node_features


def test_prepare_node_features_log1p_and_standardizes():
    x = torch.tensor([[0.0, 100.0, 0.0, 5.0, 1.0], [10.0, 400.0, 2.0, 5.0, 0.0]], dtype=torch.float)
    out = _prepare_node_features(x)
    assert out.shape == x.shape
    assert torch.isfinite(out).all()
    assert float(out[:, 0].std()) == pytest.approx(1.0, rel=0.05, abs=0.05)


def test_train_config_defaults_are_stable():
    config = TrainConfig()
    assert config.lr == 0.001
    assert config.max_grad_norm == 1.0
    assert config.weight_decay == 1e-4
    assert config.hidden == 64

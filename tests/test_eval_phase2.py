"""Tests for Phase 2 eval helpers (overfitting check, explainability integration)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_overfitting_warning_not_fatal(tmp_path, monkeypatch):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    meta = {
        "models": {
            "influence_propagation": {
                "accuracy": 0.995,
                "baseline": 0.5,
                "recovery_rate": 0.495,
            },
            "combined_adoption": {"accuracy": 0.8, "baseline": 0.5},
        }
    }
    (models_dir / "training_metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    preds = pd.DataFrame(
        {
            "user_id": ["u1"],
            "prediction_type": ["adoption"],
            "score": [0.7],
            "confidence": [0.8],
            "target_id": ["i1"],
        }
    )
    preds.to_parquet(models_dir / "predictions.parquet")

    monkeypatch.setenv("MODELS_DIR", str(models_dir))
    from scripts.check_influence_recovery import check_recovery

    errors, warnings = check_recovery()
    assert not errors
    assert any("overfitting" in w.lower() for w in warnings)


def test_strict_overfitting_fails(tmp_path, monkeypatch):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    meta = {
        "models": {
            "influence_propagation": {
                "accuracy": 0.995,
                "baseline": 0.5,
                "recovery_rate": 0.495,
            },
        }
    }
    (models_dir / "training_metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    preds = pd.DataFrame(
        {
            "user_id": ["u1"],
            "prediction_type": ["adoption"],
            "score": [0.7],
            "confidence": [0.8],
            "target_id": ["i1"],
        }
    )
    preds.to_parquet(models_dir / "predictions.parquet")

    monkeypatch.setenv("MODELS_DIR", str(models_dir))
    from scripts.check_influence_recovery import check_recovery

    errors, _warnings = check_recovery(strict_overfitting=True)
    assert errors
    assert any("overfitting" in e.lower() for e in errors)

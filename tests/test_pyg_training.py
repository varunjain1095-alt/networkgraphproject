"""Phase 2 model training tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

torch = pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

pytestmark = [pytest.mark.integration, pytest.mark.pyg]


@pytest.fixture(scope="module")
def trained_models(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("pygtrain") / "test.db"
    graphs_dir = tmp_path_factory.mktemp("g2") / "graphs"
    metrics_dir = tmp_path_factory.mktemp("m2") / "metrics"
    models_dir = tmp_path_factory.mktemp("md2") / "models"
    env = {
        **__import__("os").environ,
        "DATABASE_PATH": str(db_path),
        "GRAPHS_DIR": str(graphs_dir),
        "METRICS_DIR": str(metrics_dir),
        "MODELS_DIR": str(models_dir),
    }
    for cmd in (
        [sys.executable, str(ROOT / "generator" / "run_generator.py"), "--scale", "dev", "--seed", "21", "--force-schema"],
        [sys.executable, str(ROOT / "graphs" / "builder.py"), "--all-layers", "--clear-cache"],
        [sys.executable, str(ROOT / "analytics" / "networkx_metrics.py")],
        [sys.executable, str(ROOT / "analytics" / "pyg_models.py"), "--epochs", "60", "--seed", "21"],
    ):
        r = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr + r.stdout
    return env, models_dir


def test_training_writes_predictions(trained_models):
    _env, models_dir = trained_models
    pred_path = models_dir / "predictions.parquet"
    meta_path = models_dir / "training_metadata.json"
    assert pred_path.is_file()
    assert meta_path.is_file()


def test_training_metadata_has_recovery_metric(trained_models):
    import json

    _env, models_dir = trained_models
    meta = json.loads((models_dir / "training_metadata.json").read_text(encoding="utf-8"))
    assert "influence_propagation" in meta.get("models", {})
    influence = meta["models"]["influence_propagation"]
    assert "recovery_rate" in influence


def test_training_beats_baseline_on_dev(trained_models):
    import json

    _env, models_dir = trained_models
    meta = json.loads((models_dir / "training_metadata.json").read_text(encoding="utf-8"))
    for name, metrics in meta.get("models", {}).items():
        acc = float(metrics.get("accuracy", 0.0))
        base = float(metrics.get("baseline", 0.5))
        assert acc > base, f"{name}: accuracy {acc:.4f} not above baseline {base:.4f}"


def test_no_live_predict_in_dashboard_callbacks():
    text = (ROOT / "dashboard" / "callbacks.py").read_text(encoding="utf-8")
    assert "train_all_models" not in text
    assert "pyg_models" not in text

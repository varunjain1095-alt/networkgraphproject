"""Phase 2 pipeline and recovery check tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")


@pytest.fixture(scope="module")
def pipeline_full_env(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("full") / "test.db"
    graphs_dir = tmp_path_factory.mktemp("gf") / "graphs"
    metrics_dir = tmp_path_factory.mktemp("mf") / "metrics"
    models_dir = tmp_path_factory.mktemp("mdf") / "models"
    env = {
        **__import__("os").environ,
        "DATABASE_PATH": str(db_path),
        "GRAPHS_DIR": str(graphs_dir),
        "METRICS_DIR": str(metrics_dir),
        "MODELS_DIR": str(models_dir),
    }
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "run.py"),
        "pipeline-full",
        "--scale",
        "dev",
        "--seed",
        "21",
        "--epochs",
        "60",
    ]
    result = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    return env, models_dir


def test_pipeline_full_produces_predictions(pipeline_full_env):
    _env, models_dir = pipeline_full_env
    assert (models_dir / "predictions.parquet").is_file()
    assert (models_dir / "training_metadata.json").is_file()


def test_influence_recovery_script(pipeline_full_env):
    _env, models_dir = pipeline_full_env
    env = {**_env}
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_influence_recovery.py")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "PASSED" in result.stdout


def test_influence_recovery_metadata(pipeline_full_env):
    _env, models_dir = pipeline_full_env
    meta = json.loads((models_dir / "training_metadata.json").read_text(encoding="utf-8"))
    influence = meta["models"]["influence_propagation"]
    assert influence["accuracy"] > influence["baseline"]
    assert influence["recovery_rate"] >= 0.0

"""Phase 1G pre-bugs helper tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_forbidden_column_detection():
    sys.path.insert(0, str(ROOT))
    from scripts.audit_feature_columns import is_forbidden_column

    assert is_forbidden_column("activity_propensity")
    assert is_forbidden_column("_gen_score")
    assert is_forbidden_column("planted_influence_rule_id")
    assert not is_forbidden_column("user_id")
    assert not is_forbidden_column("metric_value")


def test_audit_passes_clean_exports(tmp_path):
    sys.path.insert(0, str(ROOT))
    import os

    metrics = tmp_path / "metrics"
    metrics.mkdir()
    df = pd.DataFrame({"user_id": ["u1"], "metric_value": [0.5]})
    df.to_parquet(metrics / "node_metrics.parquet", index=False)

    os.environ["METRICS_DIR"] = str(metrics)
    os.environ["MODELS_DIR"] = str(tmp_path / "models")

    from scripts.audit_feature_columns import audit

    assert audit() == []


def test_audit_fails_on_leaked_column(tmp_path):
    sys.path.insert(0, str(ROOT))
    import os

    metrics = tmp_path / "metrics"
    metrics.mkdir()
    df = pd.DataFrame({"user_id": ["u1"], "activity_propensity": [0.9]})
    df.to_parquet(metrics / "bad.parquet", index=False)

    os.environ["METRICS_DIR"] = str(metrics)
    os.environ["MODELS_DIR"] = str(tmp_path / "models")

    from scripts.audit_feature_columns import audit

    errors = audit()
    assert errors
    assert any("activity_propensity" in e for e in errors)


def test_audit_script_cli(tmp_path):
    metrics = tmp_path / "metrics"
    metrics.mkdir()
    pd.DataFrame({"node_id": ["u1"], "score": [1.0]}).to_parquet(metrics / "ok.parquet", index=False)
    env = {**__import__("os").environ, "METRICS_DIR": str(metrics), "MODELS_DIR": str(tmp_path / "models")}
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "audit_feature_columns.py")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "PASSED" in result.stdout


def test_check_env_git_not_tracked():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_env.py"), "--check-git"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_influence_recovery_script_missing_metadata(tmp_path):
    sys.path.insert(0, str(ROOT))
    import os

    os.environ["MODELS_DIR"] = str(tmp_path / "models")
    from scripts.check_influence_recovery import check_recovery

    errors, _warnings = check_recovery()
    assert errors
    assert any("missing" in e.lower() for e in errors)


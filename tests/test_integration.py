"""Phase 1F integration tests — full pipeline wiring."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def fresh_pipeline(tmp_path_factory):
    """Generate → validate → graphs → metrics in an isolated temp directory."""
    work = tmp_path_factory.mktemp("integration")
    db_path = work / "synthetic.db"
    graphs_dir = work / "graphs"
    metrics_dir = work / "metrics"
    env = {
        **os.environ,
        "DATABASE_PATH": str(db_path),
        "GRAPHS_DIR": str(graphs_dir),
        "METRICS_DIR": str(metrics_dir),
        "SCALE_MODE": "dev",
        "GENERATOR_SEED": "77",
    }
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "run.py"),
        "pipeline",
        "--scale",
        "dev",
        "--seed",
        "77",
    ]
    result = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    return db_path, graphs_dir, metrics_dir, env


def test_pipeline_produces_db_graphs_and_metrics(fresh_pipeline):
    db_path, graphs_dir, metrics_dir, _env = fresh_pipeline
    assert db_path.is_file()
    for name in ("layer1.gpickle", "layer2.gpickle", "layer3.gpickle", "layer4.gpickle"):
        assert (graphs_dir / name).is_file(), f"missing {name}"
    assert any(metrics_dir.iterdir()), "metrics dir empty"


def test_cache_freshness_after_pipeline(fresh_pipeline):
    db_path, graphs_dir, metrics_dir, env = fresh_pipeline
    sys.path.insert(0, str(ROOT))
    os.environ.update(env)
    from scripts.check_cache_freshness import check_freshness

    errors = check_freshness()
    assert not errors, errors


def test_use_cases_run_on_pipeline_output(fresh_pipeline):
    db_path, _graphs, _metrics, env = fresh_pipeline
    sys.path.insert(0, str(ROOT))
    os.environ.update(env)
    import sqlite3

    from use_cases.context import UseCaseContext
    from use_cases.registry import run_all

    with UseCaseContext(sqlite3.connect(db_path)) as ctx:
        ctx.conn.row_factory = sqlite3.Row
        results = run_all(ctx)

    assert len(results) == 8
    assert any(r.has_results for r in results.values())


def test_dashboard_data_ready_after_pipeline(fresh_pipeline):
    db_path, _graphs, _metrics, env = fresh_pipeline
    sys.path.insert(0, str(ROOT))
    os.environ.update(env)
    from dashboard.data_loader import DashboardData

    data = DashboardData.load()
    assert data.ready, data.error
    assert len(data.use_case_results) == 8
    assert not data.ranked_users.empty


def test_dashboard_loads_within_five_seconds(fresh_pipeline):
    db_path, _graphs, _metrics, env = fresh_pipeline
    sys.path.insert(0, str(ROOT))
    os.environ.update(env)
    from dashboard.data_loader import DashboardData

    start = time.perf_counter()
    data = DashboardData.load()
    elapsed = time.perf_counter() - start
    assert data.ready
    assert elapsed < 5.0, f"Dashboard data load took {elapsed:.2f}s (target < 5s)"


def test_pipeline_works_from_different_cwd(tmp_path):
    work = tmp_path / "remote"
    work.mkdir()
    db_path = work / "synthetic.db"
    env = {
        **os.environ,
        "DATABASE_PATH": str(db_path),
        "GRAPHS_DIR": str(work / "graphs"),
        "METRICS_DIR": str(work / "metrics"),
    }
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "run.py"),
        "pipeline",
        "--scale",
        "dev",
        "--seed",
        "88",
    ]
    result = subprocess.run(cmd, cwd=work, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert db_path.is_file()


def test_run_py_demo_prints_dashboard_hint(capsys):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run.py"), "help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "demo" in result.stdout.lower() or "dashboard" in result.stdout.lower()

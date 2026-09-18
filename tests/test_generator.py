"""Tests for synthetic data generation (dev scale)."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def dev_db(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("gen") / "test_synthetic.db"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "generator" / "run_generator.py"),
            "--seed",
            "99",
            "--scale",
            "dev",
            "--force-schema",
        ],
        cwd=ROOT,
        env={**__import__("os").environ, "DATABASE_PATH": str(db_path)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    return db_path


def test_generator_produces_users(dev_db):
    conn = sqlite3.connect(dev_db)
    n = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    assert n == 500


def test_validator_passes(dev_db):
    result = subprocess.run(
        [sys.executable, str(ROOT / "validator" / "run_validation.py"), "--all"],
        cwd=ROOT,
        env={**__import__("os").environ, "DATABASE_PATH": str(dev_db)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Validation PASSED" in result.stdout


def test_degree_skew(dev_db):
    conn = sqlite3.connect(dev_db)
    rows = conn.execute(
        """
        SELECT user_id_a u FROM relationship_edges
        UNION ALL SELECT user_id_b FROM relationship_edges
        """
    ).fetchall()
    conn.close()
    from collections import Counter

    degrees = Counter(r[0] for r in rows)
    assert max(degrees.values()) > 20

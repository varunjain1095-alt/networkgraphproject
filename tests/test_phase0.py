"""Phase 0 setup tests."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_domain_config_loads():
    with (ROOT / "domain_config.yaml").open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    assert config["default_domain"] == "gaming"
    assert "gaming" in config["domains"]
    assert config["domains"]["gaming"]["entities"]["item"] == "Game"


def test_config_domain_module():
    sys.path.insert(0, str(ROOT))
    from config.domain import entity_label, load_domain_config

    config = load_domain_config()
    assert entity_label("item", config) == "Game"


def test_init_db_creates_tables(tmp_path):
    sys.path.insert(0, str(ROOT))
    from scripts.init_db import EXPECTED_TABLES, init_db

    db_path = tmp_path / "test.db"
    init_db(db_path=db_path, force=True)

    with sqlite3.connect(db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchone()[0]
    assert count >= EXPECTED_TABLES


def test_init_db_works_from_different_cwd(tmp_path):
    db_path = tmp_path / "remote.db"
    env = os.environ.copy()
    env["DATABASE_PATH"] = str(db_path)

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "init_db.py"), "--force", "--db", str(db_path)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert db_path.is_file()


def test_check_env_script():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_env.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr

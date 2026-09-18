"""Phase 0 end-to-end smoke test — config, env, database."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.domain import entity_label, get_active_domain, load_domain_config
from config.env import load_env, project_root, resolve_path
from scripts.init_db import EXPECTED_TABLES, init_db


def run_smoke(force_db: bool = False) -> list[str]:
    errors: list[str] = []

    load_env()
    root = project_root()
    if not root.is_dir():
        errors.append(f"Project root not found: {root}")

    try:
        config = load_domain_config()
        domain = get_active_domain(config)
        label = entity_label("item", config)
        if not label:
            errors.append("entity_label returned empty string")
        elif not domain.get("display_name"):
            errors.append("active domain missing display_name")
    except Exception as exc:
        errors.append(f"domain config: {exc}")

    try:
        db_path = resolve_path("DATABASE_PATH", "data/synthetic.db")
        if not db_path.exists() or force_db:
            db_path = init_db(force=force_db)
        with sqlite3.connect(db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchone()[0]
            if count < EXPECTED_TABLES:
                errors.append(f"expected {EXPECTED_TABLES}+ tables, found {count}")
    except Exception as exc:
        errors.append(f"database: {exc}")

    data_dir = resolve_path("DATA_DIR", "data")
    if not data_dir.is_dir():
        errors.append(f"DATA_DIR missing: {data_dir}")

    return errors


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Phase 0 smoke test")
    parser.add_argument("--force-db", action="store_true", help="Recreate database")
    args = parser.parse_args()

    errors = run_smoke(force_db=args.force_db)
    if errors:
        print("Smoke test FAILED:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("Smoke test PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

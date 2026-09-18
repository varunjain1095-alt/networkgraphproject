"""Validate generated synthetic dataset."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.env import load_env, resolve_path
from generator.db_utils import connect
from validator.checks import distribution_snapshot, run_all_checks


def config_hash() -> str:
    domain_path = Path(__file__).resolve().parents[1] / "domain_config.yaml"
    return hashlib.sha256(domain_path.read_bytes()).hexdigest()[:16]


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser(description="Validate synthetic dataset")
    parser.add_argument("--all", action="store_true", help="Run all checks")
    parser.add_argument("--check", choices=["row_counts", "distribution", "timestamps", "foreign_keys"])
    args = parser.parse_args()

    db_path = resolve_path("DATABASE_PATH", "data/synthetic.db")
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return 1

    conn = connect(db_path)
    try:
        if args.check:
            from validator import checks as c

            fn = {
                "row_counts": c.check_row_counts,
                "distribution": c.check_degree_distribution,
                "timestamps": c.check_timestamps,
                "foreign_keys": c.check_foreign_keys,
            }[args.check]
            results = [fn(conn)]
        else:
            results = run_all_checks(conn, config_hash=config_hash())

        failed = 0
        for r in results:
            status = "PASS" if r.passed else "FAIL"
            print(f"[{status}] {r.name}: {r.message}")
            if not r.passed:
                failed += 1

        if args.all or not args.check:
            print(distribution_snapshot(conn))

        if failed:
            print(f"\nValidation FAILED ({failed} check(s))")
            return 1

        print("\nValidation PASSED")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())

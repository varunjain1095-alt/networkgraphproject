"""Pre-bugs helper — verify graph/metrics cache is newer than database."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.env import load_env, resolve_path
from graphs.settings import LAYER_FILES


def _parse_iso_timestamp(value: str) -> float:
    text = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def reference_timestamp(db_path: Path) -> float:
    """Use dataset generation time — DB file mtime changes when metrics are written."""
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT generated_at FROM dataset_metadata WHERE dataset_id = 1"
        ).fetchone()
    if row and row[0]:
        return _parse_iso_timestamp(row[0])
    return db_path.stat().st_mtime


def check_freshness(pre: bool = False) -> list[str]:
    errors: list[str] = []
    db_path = resolve_path("DATABASE_PATH", "data/synthetic.db")
    graphs_dir = resolve_path("GRAPHS_DIR", "data/graphs")

    if not db_path.is_file():
        errors.append(f"Database not found: {db_path}")
        return errors

    ref_mtime = reference_timestamp(db_path)

    for filename in LAYER_FILES:
        cache_path = graphs_dir / filename
        if not cache_path.is_file():
            errors.append(f"Missing cache file: {cache_path}")
            continue
        if cache_path.stat().st_mtime < ref_mtime:
            errors.append(f"Stale cache (older than dataset): {filename}")

    if pre:
        return errors

    metrics_dir = resolve_path("METRICS_DIR", "data/metrics")
    if metrics_dir.is_dir():
        metric_files = [p for p in metrics_dir.glob("*") if p.is_file()]
        if not metric_files:
            errors.append(f"No metrics files in {metrics_dir}")
        else:
            for metric_file in metric_files:
                if metric_file.stat().st_mtime < ref_mtime:
                    errors.append(f"Stale metrics file: {metric_file.name}")

    return errors


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser(description="Check cache freshness vs database")
    parser.add_argument("--pre", action="store_true", help="Only check graph cache (pre-pipeline)")
    args = parser.parse_args()

    errors = check_freshness(pre=args.pre)
    if errors:
        print("Cache freshness FAILED:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("Cache freshness PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Performance smoke — dashboard data load target (Phase 1F/1G)."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.env import load_env
from dashboard.data_loader import DashboardData

MAX_LOAD_SECONDS = 5.0


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser(description="Dashboard load performance smoke test")
    parser.add_argument("--max-seconds", type=float, default=MAX_LOAD_SECONDS)
    args = parser.parse_args()

    start = time.perf_counter()
    data = DashboardData.load()
    elapsed = time.perf_counter() - start

    if not data.ready:
        print(f"perf_smoke FAILED: {data.error}")
        return 1

    print(f"Dashboard data load: {elapsed:.2f}s (target < {args.max_seconds}s)")
    print(f"  users ranked: {len(data.ranked_users)}")
    print(f"  use cases: {len(data.use_case_results)}")

    if elapsed >= args.max_seconds:
        print("perf_smoke FAILED: load time exceeded target")
        return 1

    print("perf_smoke PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Compute and cache NetworkX structural metrics (Phase 1C)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analytics.compute import compute_all_metrics
from config.env import get, load_env


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser(description="Compute NetworkX metrics for all graph layers")
    parser.add_argument("--seed", type=int, default=int(get("GENERATOR_SEED", "42") or 42))
    args = parser.parse_args()

    try:
        compute_all_metrics(seed=args.seed)
        return 0
    except FileNotFoundError as exc:
        print(f"Metrics compute FAILED: {exc}", file=sys.stderr)
        print("Run: python graphs/builder.py --all-layers", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Metrics compute FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

"""Run all use cases and print summary."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.env import load_env
from use_cases.registry import run_all


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser(description="Run all use case modules")
    parser.add_argument("--least", action="store_true", help="Show least important first")
    args = parser.parse_args()

    try:
        results = run_all(most_important=not args.least)
    except FileNotFoundError as exc:
        print(f"Use cases FAILED: {exc}", file=sys.stderr)
        print("Run metrics compute first: python analytics/networkx_metrics.py", file=sys.stderr)
        return 1

    print(f"\n{'Use case':<25} {'Flagged':>8}  Sample")
    print("-" * 60)
    for uc_id, result in results.items():
        count = len(result.flagged)
        sample = result.flagged[0].label if result.flagged else result.empty_message or "—"
        print(f"{result.title:<25} {count:>8}  {sample[:40]}")

    empty = [r for r in results.values() if not r.has_results and not r.empty_message]
    if empty:
        print("\nWARNING: some use cases returned empty without empty_message")
        return 1

    print("\nAll use cases completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

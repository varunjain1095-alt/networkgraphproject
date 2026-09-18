"""Full project eval — Phase 1 + Phase 2 sign-off (evals.md)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def main() -> int:
    parser = argparse.ArgumentParser(description="Run full project eval gate")
    parser.add_argument("--skip-integration", action="store_true")
    parser.add_argument("--skip-training-tests", action="store_true")
    args = parser.parse_args()

    phase1_extra = []
    if args.skip_integration:
        phase1_extra.append("--skip-integration")

    phase2_extra = list(phase1_extra)
    if args.skip_training_tests:
        phase2_extra.append("--skip-training-tests")

    steps = [
        ([PYTHON, str(ROOT / "scripts" / "eval_phase1.py"), *phase1_extra], "Phase 1"),
        ([PYTHON, str(ROOT / "scripts" / "eval_phase2.py"), *phase2_extra], "Phase 2"),
    ]

    for cmd, name in steps:
        print(f"\n{'=' * 60}\n{name} eval\n{'=' * 60}")
        result = subprocess.run(cmd, cwd=ROOT)
        if result.returncode != 0:
            print(f"\nProject eval FAILED at {name}", file=sys.stderr)
            return 1

    print("\n" + "=" * 60)
    print("PROJECT AUTOMATED EVAL PASSED")
    print("=" * 60)
    print("\nManual sign-off remaining (evals.md):")
    print("  1. Phase 1E dashboard spot-check (12 items)")
    print("  2. Phase 2 dashboard spot-check (predictions + layer breakdown)")
    print("  3. Optional 'fresh eyes' test with someone unfamiliar with the project")
    return 0


if __name__ == "__main__":
    sys.exit(main())

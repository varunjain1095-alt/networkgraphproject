"""Phase 1 eval gate — automated checks from evals.md before Phase 2."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run(label: str, cmd: list[str]) -> bool:
    print(f"\n== {label} ==")
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip(), file=sys.stderr)
    ok = result.returncode == 0
    if not ok:
        print(f"FAILED: {label}", file=sys.stderr)
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 1 eval gate (automated portion of evals.md)")
    parser.add_argument("--skip-integration", action="store_true")
    args = parser.parse_args()

    checks = [
        ("Pre-bugs runbook", [PYTHON, str(ROOT / "scripts" / "pre_bugs.py"), "--skip-graphs"]),
        ("Unit tests", [PYTHON, "-m", "pytest", "tests/", "-m", "not integration", "-q"]),
    ]
    if not args.skip_integration:
        checks.append(("Integration tests", [PYTHON, "-m", "pytest", "tests/test_integration.py", "-q"]))

    failures = [label for label, cmd in checks if not run(label, cmd)]

    print("\n--- Phase 1E manual spot-check (browser) ---")
    print("Open http://127.0.0.1:8050 and verify evals.md items 1-12:")
    print("  ranked list -> graph -> explanation, search, layers, use cases, layer 3 table")

    if failures:
        print("\nPhase 1 eval gate FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("\nPhase 1 automated eval gate PASSED")
    print("Complete manual spot-check from evals.md to mark Phase 1 demo-ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

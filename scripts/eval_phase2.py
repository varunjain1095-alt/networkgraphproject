"""Phase 2 eval gate — automated checks from evals.md (project completion)."""

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


def grep_clean(label: str, pattern: str, path: str) -> bool:
    target = ROOT / path
    if not target.is_file():
        return True
    if pattern in target.read_text(encoding="utf-8"):
        print(f"FAILED: {label}: found '{pattern}' in {path}", file=sys.stderr)
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 2 eval gate (evals.md)")
    parser.add_argument("--skip-integration", action="store_true")
    parser.add_argument("--skip-training-tests", action="store_true", help="Skip slow PyG training tests")
    args = parser.parse_args()

    failures: list[str] = []

    checks = [
        ("Phase 2 pre-bugs", [PYTHON, str(ROOT / "scripts" / "pre_bugs.py"), "--phase2", "--skip-graphs"]),
        ("Influence recovery", [PYTHON, str(ROOT / "scripts" / "check_influence_recovery.py")]),
        ("Feature audit (Phase 2)", [PYTHON, str(ROOT / "scripts" / "audit_feature_columns.py"), "--phase2"]),
        ("PyG conversion tests", [PYTHON, "-m", "pytest", "tests/test_pyg.py", "-q"]),
    ]
    if not args.skip_training_tests:
        checks.append(
            ("PyG training tests", [PYTHON, "-m", "pytest", "tests/test_pyg_training.py", "-q"]),
        )
    if not args.skip_integration:
        checks.append(
            ("Phase 2 pipeline tests", [PYTHON, "-m", "pytest", "tests/test_phase2_pipeline.py", "-q"]),
        )

    for label, cmd in checks:
        if not run(label, cmd):
            failures.append(label)

    grep_checks = [
        ("No live GNN training in dashboard", "train_all_models", "dashboard/callbacks.py"),
        ("No live GNN training in dashboard", "pyg_models", "dashboard/callbacks.py"),
        ("No live torch.load in dashboard", "torch.load", "dashboard/callbacks.py"),
    ]
    for label, pattern, path in grep_checks:
        if not grep_clean(label, pattern, path):
            failures.append(label)

    # Explainability module present
    if not (ROOT / "dashboard" / "layer_contributions.py").is_file():
        failures.append("layer_contributions.py missing")

    print("\n--- Phase 2 dashboard spot-check (browser) ---")
    print("After training, open http://127.0.0.1:8050 and verify:")
    print("  explainability shows predictions + confidence + layer breakdown")
    print("  champion churn and rollout use cases mention forward-looking scores")

    if failures:
        print("\nPhase 2 eval gate FAILED:")
        for item in failures:
            print(f"  - {item}")
        return 1

    print("\nPhase 2 automated eval gate PASSED")
    print("Project automated checks complete. Run manual spot-check for PM legibility.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Phase 1G + Phase 2 pre-bugs runbook."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def _run_step(
    label: str,
    cmd: list[str],
    *,
    cwd: Path | None = None,
    stream: bool = False,
) -> tuple[bool, str]:
    print(f"\n== {label} ==")
    print(f"> {' '.join(cmd)}")
    if stream:
        result = subprocess.run(cmd, cwd=cwd or ROOT)
        return result.returncode == 0, ""

    result = subprocess.run(cmd, cwd=cwd or ROOT, capture_output=True, text=True)
    output = (result.stdout or "") + (result.stderr or "")
    if output.strip():
        print(output.rstrip())
    ok = result.returncode == 0
    if not ok:
        print(f"FAILED: {label} (exit {result.returncode})", file=sys.stderr)
    return ok, output


def _metrics_cache_ready() -> bool:
    sys.path.insert(0, str(ROOT))
    from scripts.check_cache_freshness import check_freshness

    import sqlite3

    from config.env import load_env, resolve_path

    load_env()
    db_path = resolve_path("DATABASE_PATH", "data/synthetic.db")
    if not db_path.is_file():
        return False
    if check_freshness(pre=False):
        return False
    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM node_metrics").fetchone()[0]
    return count > 0


def _print_scale_runtime_warning() -> None:
    sys.path.insert(0, str(ROOT))
    import sqlite3

    from config.env import load_env, resolve_path

    load_env()
    db_path = resolve_path("DATABASE_PATH", "data/synthetic.db")
    if not db_path.is_file():
        return
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
    n_users = row[0] if row else 0
    if n_users >= 8_000:
        print(
            "\n*** RUNTIME WARNING: demo-scale dataset (~10k users). "
            "Metrics compute can take 2-4+ HOURS and shows no live output unless run directly. "
            "For visual testing after pipeline, skip pre-bugs and run: python scripts/run.py dashboard ***\n"
        )
    elif n_users >= 2_000:
        print(
            "\n*** NOTE: medium-scale dataset (~2.5k users). "
            "Metrics compute typically takes 20-60 minutes. ***\n"
        )


def _grep_clean(label: str, pattern: str, path: str) -> tuple[bool, str]:
    target = ROOT / path
    if not target.is_file():
        return True, ""
    text = target.read_text(encoding="utf-8")
    if pattern in text:
        return False, f"{label}: found '{pattern}' in {path}"
    return True, ""


def _torch_available() -> bool:
    try:
        import torch  # noqa: F401
        import torch_geometric  # noqa: F401

        return True
    except ImportError:
        return False


def run_pre_bugs(
    *,
    skip_graphs: bool = False,
    skip_integration: bool = False,
    skip_perf: bool = False,
    skip_metrics: bool = False,
    phase2: bool = False,
) -> list[str]:
    failures: list[str] = []

    _print_scale_runtime_warning()

    steps: list[tuple[str, list[str], bool]] = [
        ("Data validation", [PYTHON, str(ROOT / "validator" / "run_validation.py"), "--all"], False),
    ]
    if not skip_graphs:
        steps.append(
            ("Cache freshness (pre-metrics)", [PYTHON, str(ROOT / "scripts" / "check_cache_freshness.py"), "--pre"], False)
        )
        steps.append(
            ("Graph build", [PYTHON, str(ROOT / "graphs" / "builder.py"), "--all-layers", "--clear-cache"], False)
        )
    steps.extend(
        [
            ("Graph tests", [PYTHON, "-m", "pytest", "tests/test_graphs.py", "-q"], False),
        ]
    )

    if skip_metrics:
        if _metrics_cache_ready():
            print("\n== Metrics compute SKIPPED (fresh cache on disk) ==")
        else:
            failures.append("Metrics compute skipped but no fresh metrics cache found")
    else:
        steps.append(
            (
                "Metrics compute",
                [PYTHON, "-u", str(ROOT / "analytics" / "networkx_metrics.py")],
                True,
            )
        )

    steps.extend(
        [
            ("Cache freshness (post-metrics)", [PYTHON, str(ROOT / "scripts" / "check_cache_freshness.py")], False),
            ("Metrics tests", [PYTHON, "-m", "pytest", "tests/test_metrics.py", "-q"], False),
            ("Use case tests", [PYTHON, "-m", "pytest", "tests/test_use_cases.py", "-q"], False),
            ("Dashboard callback tests", [PYTHON, "-m", "pytest", "tests/test_dashboard_callbacks.py", "-q"], False),
            ("Pre-bugs helper tests", [PYTHON, "-m", "pytest", "tests/test_pre_bugs.py", "-q"], False),
            (
                "Feature column audit",
                [PYTHON, str(ROOT / "scripts" / "audit_feature_columns.py")]
                + (["--phase2"] if phase2 else []),
                False,
            ),
        ]
    )

    if phase2:
        if _torch_available():
            steps.extend(
                [
                    ("PyG conversion tests", [PYTHON, "-m", "pytest", "tests/test_pyg.py", "-q"], False),
                    ("PyG training tests", [PYTHON, "-m", "pytest", "tests/test_pyg_training.py", "-q"], False),
                ]
            )
        else:
            print("\n== PyG tests skipped (torch not installed) ==")
        steps.append(
            ("Influence recovery check", [PYTHON, str(ROOT / "scripts" / "check_influence_recovery.py")], False)
        )

    if not skip_integration:
        marker = "integration" if not phase2 else "integration"
        steps.append(("Integration tests", [PYTHON, "-m", "pytest", "tests/", "-m", marker, "-q"], False))

    if not skip_perf:
        steps.append(("Performance smoke", [PYTHON, str(ROOT / "scripts" / "perf_smoke.py")], False))

    steps.append(("Environment check", [PYTHON, str(ROOT / "scripts" / "check_env.py"), "--check-git"], False))

    for label, cmd, stream in steps:
        ok, _ = _run_step(label, cmd, stream=stream)
        if not ok:
            failures.append(label)

    grep_checks = [
        ("No live betweenness in dashboard", "betweenness_centrality", "dashboard/callbacks.py"),
        ("No live GNN training in dashboard", "train_all_models", "dashboard/callbacks.py"),
        ("No live GNN training in dashboard", "pyg_models", "dashboard/callbacks.py"),
    ]
    if phase2:
        grep_checks.append(("No live GNN predict in dashboard", "torch.load", "dashboard/callbacks.py"))

    for label, pattern, path in grep_checks:
        ok, msg = _grep_clean(label, pattern, path)
        if not ok:
            failures.append(msg)

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Run pre-bugs checklist (Phase 1G / Phase 2)")
    parser.add_argument("--skip-graphs", action="store_true", help="Skip graph rebuild (use existing cache)")
    parser.add_argument("--skip-metrics", action="store_true", help="Skip metrics recompute when fresh cache exists")
    parser.add_argument("--skip-integration", action="store_true", help="Skip integration tests")
    parser.add_argument("--skip-perf", action="store_true", help="Skip performance smoke test")
    parser.add_argument("--phase2", action="store_true", help="Include Phase 2 audits and PyG checks")
    args = parser.parse_args()

    failures = run_pre_bugs(
        skip_graphs=args.skip_graphs,
        skip_metrics=args.skip_metrics,
        skip_integration=args.skip_integration,
        skip_perf=args.skip_perf,
        phase2=args.phase2,
    )
    if failures:
        title = "Phase 2 pre-bugs runbook FAILED" if args.phase2 else "Pre-bugs runbook FAILED"
        print(f"\n{title}:")
        for item in failures:
            print(f"  - {item}")
        return 1

    title = "Phase 2 pre-bugs runbook PASSED" if args.phase2 else "Pre-bugs runbook PASSED"
    print(f"\n{title}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

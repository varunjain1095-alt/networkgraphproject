"""Cross-platform CLI for pipeline commands (Phase 0+)."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.pipeline_lib import run_full_pipeline, run_pipeline


def _run(script: str, *args: str) -> int:
    cmd = [PYTHON, str(ROOT / script), *args]
    print(f"> {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=ROOT)


def cmd_check_env(_: argparse.Namespace) -> int:
    return _run("scripts/check_env.py")


def cmd_init_db(args: argparse.Namespace) -> int:
    extra = ["--force"] if args.force else []
    return _run("scripts/init_db.py", *extra)


def cmd_smoke(args: argparse.Namespace) -> int:
    extra = ["--force-db"] if args.force else []
    return _run("scripts/smoke_test.py", *extra)


def cmd_generate(args: argparse.Namespace) -> int:
    extra = ["--scale", args.scale]
    if args.seed is not None:
        extra.extend(["--seed", str(args.seed)])
    if args.force_schema:
        extra.append("--force-schema")
    return _run("generator/run_generator.py", *extra)


def cmd_validate(_: argparse.Namespace) -> int:
    return _run("validator/run_validation.py", "--all")


def cmd_graphs(args: argparse.Namespace) -> int:
    extra = ["--all-layers"]
    if args.clear_cache:
        extra.append("--clear-cache")
    return _run("graphs/builder.py", *extra)


def cmd_metrics(_: argparse.Namespace) -> int:
    return _run("analytics/networkx_metrics.py")


def cmd_use_cases(_: argparse.Namespace) -> int:
    return _run("use_cases/run_all.py")


def cmd_dashboard(_: argparse.Namespace) -> int:
    return _run("dashboard/app.py")


def cmd_train_models(args: argparse.Namespace) -> int:
    extra = []
    if args.epochs is not None:
        extra.extend(["--epochs", str(args.epochs)])
    if args.seed is not None:
        extra.extend(["--seed", str(args.seed)])
    return _run("analytics/pyg_models.py", *extra)


def cmd_pyg_export(_: argparse.Namespace) -> int:
    return _run("analytics/pyg_export.py", "--all-layers")


def cmd_eval_phase1(args: argparse.Namespace) -> int:
    extra = []
    if args.skip_integration:
        extra.append("--skip-integration")
    return _run("scripts/eval_phase1.py", *extra)


def cmd_eval_phase2(args: argparse.Namespace) -> int:
    extra = []
    if args.skip_integration:
        extra.append("--skip-integration")
    if args.skip_training_tests:
        extra.append("--skip-training-tests")
    return _run("scripts/eval_phase2.py", *extra)


def cmd_eval_project(args: argparse.Namespace) -> int:
    extra = []
    if args.skip_integration:
        extra.append("--skip-integration")
    if args.skip_training_tests:
        extra.append("--skip-training-tests")
    return _run("scripts/eval_project.py", *extra)


def cmd_check_cache(_: argparse.Namespace) -> int:
    return _run("scripts/check_cache_freshness.py")


def cmd_perf_smoke(args: argparse.Namespace) -> int:
    extra = []
    if args.max_seconds is not None:
        extra.extend(["--max-seconds", str(args.max_seconds)])
    return _run("scripts/perf_smoke.py", *extra)


def cmd_pre_bugs(args: argparse.Namespace) -> int:
    extra = []
    if args.skip_graphs:
        extra.append("--skip-graphs")
    if args.skip_integration:
        extra.append("--skip-integration")
    if args.skip_perf:
        extra.append("--skip-perf")
    if getattr(args, "phase2", False):
        extra.append("--phase2")
    return _run("scripts/pre_bugs.py", *extra)


def cmd_pipeline(args: argparse.Namespace) -> int:
    env = os.environ.copy()
    if args.database:
        env["DATABASE_PATH"] = args.database
    if args.graphs_dir:
        env["GRAPHS_DIR"] = args.graphs_dir
    if args.metrics_dir:
        env["METRICS_DIR"] = args.metrics_dir
    try:
        run_pipeline(scale=args.scale, seed=args.seed, env=env)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("\nPipeline complete.")
    return 0


def cmd_pipeline_full(args: argparse.Namespace) -> int:
    env = os.environ.copy()
    if args.database:
        env["DATABASE_PATH"] = args.database
    if args.graphs_dir:
        env["GRAPHS_DIR"] = args.graphs_dir
    if args.metrics_dir:
        env["METRICS_DIR"] = args.metrics_dir
    epochs = args.epochs if args.epochs is not None else 40
    try:
        run_full_pipeline(
            scale=args.scale,
            seed=args.seed,
            env=env,
            train_epochs=epochs,
            skip_train=args.skip_train,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("\nFull pipeline complete (Phase 1 + Phase 2 training).")
    print("Start dashboard: python scripts/run.py dashboard")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    if cmd_pipeline(args) != 0:
        return 1
    print("\nDemo data is ready. Start the dashboard with:")
    print("  python scripts/run.py dashboard")
    print("  -> http://127.0.0.1:8050")
    if args.dashboard:
        return cmd_dashboard(args)
    return 0


def cmd_help(_: argparse.Namespace) -> int:
    print(
        """Network Graph Intelligence - commands

  check-env    Validate .env and paths
  init-db      Create empty SQLite schema
  smoke        Phase 0 smoke test (config + db)
  generate     Synthetic data generation (Phase 1A)
  validate     Data validation (Phase 1A)
  graphs       Build graph layers (Phase 1B)
  metrics      Compute NetworkX metrics (Phase 1C)
  use-cases    Run all use case modules (Phase 1D)
  dashboard    Start Plotly Dash app (Phase 1E)
  check-cache  Verify graph/metrics cache is newer than DB
  perf-smoke   Dashboard load time smoke test (< 5s target)
  pre-bugs     Phase 1G automated checklist (bugs.md §12)
  eval-phase1  Phase 1 automated eval gate before Phase 2
  eval-phase2  Phase 2 automated eval gate (project completion)
  eval-project Full project sign-off (Phase 1 + Phase 2)
  pyg-export   Export graphs to PyG format (Phase 2.1)
  train-models Train Phase 2 GNN models and cache predictions
  pipeline     generate -> validate -> graphs -> metrics
  pipeline-full  Phase 1 pipeline + train-models + recovery check
  demo         pipeline (dev scale) + dashboard instructions

Examples:
  python scripts/run.py check-env
  python scripts/run.py demo
  python scripts/run.py pipeline-full --scale dev --seed 42
  python scripts/run.py pre-bugs --phase2 --skip-graphs
  python scripts/run.py dashboard
"""
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Network Graph Intelligence CLI")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("help", help="Show available commands").set_defaults(func=cmd_help)
    sub.add_parser("check-env", help="Validate .env").set_defaults(func=cmd_check_env)

    init_p = sub.add_parser("init-db", help="Initialize database schema")
    init_p.add_argument("--force", action="store_true")
    init_p.set_defaults(func=cmd_init_db)

    smoke_p = sub.add_parser("smoke", help="Run Phase 0 smoke test")
    smoke_p.add_argument("--force", action="store_true")
    smoke_p.set_defaults(func=cmd_smoke)

    gen_p = sub.add_parser("generate", help="Generate synthetic data")
    gen_p.add_argument("--scale", default="dev", choices=["dev", "medium", "demo"])
    gen_p.add_argument("--seed", type=int, default=None)
    gen_p.add_argument("--force-schema", action="store_true")
    gen_p.set_defaults(func=cmd_generate, clear_cache=False)

    graphs_p = sub.add_parser("graphs", help="Build graph layers")
    graphs_p.add_argument("--clear-cache", action="store_true")
    graphs_p.set_defaults(func=cmd_graphs, scale="dev", seed=None, force_schema=False)

    for name, func in (
        ("validate", cmd_validate),
        ("metrics", cmd_metrics),
        ("use-cases", cmd_use_cases),
        ("dashboard", cmd_dashboard),
        ("check-cache", cmd_check_cache),
    ):
        sub.add_parser(name).set_defaults(
            func=func, scale="dev", seed=None, force_schema=False, clear_cache=False, dashboard=False,
            skip_graphs=False, skip_integration=False, skip_perf=False,
        )

    perf_p = sub.add_parser("perf-smoke", help="Dashboard load performance test")
    perf_p.add_argument("--max-seconds", type=float, default=None)
    perf_p.set_defaults(
        func=cmd_perf_smoke, scale="dev", seed=None, force_schema=False, clear_cache=False, dashboard=False,
        skip_graphs=False, skip_integration=False, skip_perf=False,
    )

    pre_p = sub.add_parser("pre-bugs", help="Run Phase 1G/2 pre-bugs checklist")
    pre_p.add_argument("--skip-graphs", action="store_true")
    pre_p.add_argument("--skip-integration", action="store_true")
    pre_p.add_argument("--skip-perf", action="store_true")
    pre_p.add_argument("--phase2", action="store_true", help="Include Phase 2 audits and PyG checks")
    pre_p.set_defaults(
        func=cmd_pre_bugs, scale="dev", seed=None, force_schema=False, clear_cache=False, dashboard=False,
        skip_graphs=False, skip_integration=False, skip_perf=False, phase2=False,
    )

    eval_p = sub.add_parser("eval-phase1", help="Phase 1 automated eval gate")
    eval_p.add_argument("--skip-integration", action="store_true")
    eval_p.set_defaults(
        func=cmd_eval_phase1, scale="dev", seed=None, force_schema=False, clear_cache=False, dashboard=False,
        skip_graphs=False, skip_integration=False, skip_perf=False, skip_training_tests=False,
    )

    eval2_p = sub.add_parser("eval-phase2", help="Phase 2 automated eval gate")
    eval2_p.add_argument("--skip-integration", action="store_true")
    eval2_p.add_argument("--skip-training-tests", action="store_true")
    eval2_p.set_defaults(
        func=cmd_eval_phase2, scale="dev", seed=None, force_schema=False, clear_cache=False, dashboard=False,
        skip_graphs=False, skip_integration=False, skip_perf=False, skip_training_tests=False,
    )

    eval_proj_p = sub.add_parser("eval-project", help="Full project automated eval (Phase 1 + Phase 2)")
    eval_proj_p.add_argument("--skip-integration", action="store_true")
    eval_proj_p.add_argument("--skip-training-tests", action="store_true")
    eval_proj_p.set_defaults(
        func=cmd_eval_project, scale="dev", seed=None, force_schema=False, clear_cache=False, dashboard=False,
        skip_graphs=False, skip_integration=False, skip_perf=False, skip_training_tests=False,
    )

    sub.add_parser("pyg-export", help="Export NetworkX graphs to PyG (Phase 2.1)").set_defaults(
        func=cmd_pyg_export, scale="dev", seed=None, force_schema=False, clear_cache=False, dashboard=False,
        skip_graphs=False, skip_integration=False, skip_perf=False, epochs=None,
    )

    train_p = sub.add_parser("train-models", help="Train Phase 2 PyG models")
    train_p.add_argument("--epochs", type=int, default=None)
    train_p.add_argument("--seed", type=int, default=None)
    train_p.set_defaults(
        func=cmd_train_models, scale="dev", force_schema=False, clear_cache=False, dashboard=False,
        skip_graphs=False, skip_integration=False, skip_perf=False,
    )

    pipe_p = sub.add_parser("pipeline", help="Run generate -> validate -> graphs -> metrics")
    pipe_p.add_argument("--scale", default="dev", choices=["dev", "medium", "demo"])
    pipe_p.add_argument("--seed", type=int, default=None)
    pipe_p.add_argument("--database", help="Override DATABASE_PATH for this run")
    pipe_p.add_argument("--graphs-dir", help="Override GRAPHS_DIR for this run")
    pipe_p.add_argument("--metrics-dir", help="Override METRICS_DIR for this run")
    pipe_p.set_defaults(func=cmd_pipeline, force_schema=False, clear_cache=False, dashboard=False,
                        skip_graphs=False, skip_integration=False, skip_perf=False, skip_train=False)

    full_p = sub.add_parser("pipeline-full", help="Phase 1 pipeline + train-models + recovery check")
    full_p.add_argument("--scale", default="dev", choices=["dev", "medium", "demo"])
    full_p.add_argument("--seed", type=int, default=None)
    full_p.add_argument("--epochs", type=int, default=None, help="Training epochs (default 40)")
    full_p.add_argument("--database", help="Override DATABASE_PATH for this run")
    full_p.add_argument("--graphs-dir", help="Override GRAPHS_DIR for this run")
    full_p.add_argument("--metrics-dir", help="Override METRICS_DIR for this run")
    full_p.add_argument("--skip-train", action="store_true", help="Run Phase 1 steps only")
    full_p.set_defaults(func=cmd_pipeline_full, force_schema=False, clear_cache=False, dashboard=False,
                        skip_graphs=False, skip_integration=False, skip_perf=False, skip_train=False)

    demo_p = sub.add_parser("demo", help="Run dev pipeline and print dashboard instructions")
    demo_p.add_argument("--scale", default="dev", choices=["dev", "medium", "demo"])
    demo_p.add_argument("--seed", type=int, default=42)
    demo_p.add_argument("--database", default=None)
    demo_p.add_argument("--graphs-dir", default=None)
    demo_p.add_argument("--metrics-dir", default=None)
    demo_p.add_argument("--dashboard", action="store_true", help="Start dashboard after pipeline")
    demo_p.set_defaults(func=cmd_demo, force_schema=False, clear_cache=False,
                        skip_graphs=False, skip_integration=False, skip_perf=False)

    args = parser.parse_args()
    if not args.command:
        return cmd_help(args)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

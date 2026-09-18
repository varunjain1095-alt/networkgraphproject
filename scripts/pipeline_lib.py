"""Shared end-to-end pipeline steps (Phase 1F + Phase 2)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable

PIPELINE_STEPS = (
    ("generate", [str(ROOT / "generator" / "run_generator.py"), "--force-schema"]),
    ("validate", [str(ROOT / "validator" / "run_validation.py"), "--all"]),
    ("graphs", [str(ROOT / "graphs" / "builder.py"), "--all-layers", "--clear-cache"]),
    ("metrics", [str(ROOT / "analytics" / "networkx_metrics.py")]),
)


def run_step(name: str, argv: list[str], *, env: dict[str, str] | None = None) -> None:
    cmd = [PYTHON, *argv]
    print(f"\n== pipeline: {name} ==")
    print(f"> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.rstrip())
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr.rstrip(), file=sys.stderr)
        raise RuntimeError(f"Pipeline step '{name}' failed with exit code {result.returncode}")


def run_pipeline(*, scale: str = "dev", seed: int | None = None, env: dict[str, str] | None = None) -> None:
    """Run generate → validate → graphs → metrics."""
    run_env = {**os.environ, **(env or {})}
    run_env["SCALE_MODE"] = scale
    if seed is not None:
        run_env["GENERATOR_SEED"] = str(seed)

    for name, argv in PIPELINE_STEPS:
        step_argv = list(argv)
        if name == "generate":
            step_argv.extend(["--scale", scale])
            if seed is not None:
                step_argv.extend(["--seed", str(seed)])
        run_step(name, step_argv, env=run_env)


def run_full_pipeline(
    *,
    scale: str = "dev",
    seed: int | None = None,
    env: dict[str, str] | None = None,
    train_epochs: int = 40,
    skip_train: bool = False,
) -> None:
    """Run Phase 1 pipeline then Phase 2 model training."""
    run_pipeline(scale=scale, seed=seed, env=env)
    if skip_train:
        return

    run_env = {**os.environ, **(env or {})}
    train_argv = [str(ROOT / "analytics" / "pyg_models.py"), "--epochs", str(train_epochs)]
    if seed is not None:
        train_argv.append("--seed")
        train_argv.append(str(seed))
    run_step("train-models", train_argv, env=run_env)

    recovery_argv = [str(ROOT / "scripts" / "check_influence_recovery.py")]
    run_step("influence-recovery", recovery_argv, env=run_env)

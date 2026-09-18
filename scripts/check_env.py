"""Validate .env configuration (paths and runtime settings). No external APIs."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.env import get, load_env, project_root, resolve_path

REQUIRED = ("DATABASE_PATH", "DATA_DIR", "DASH_HOST", "DASH_PORT")


def check_config() -> list[str]:
    errors: list[str] = []
    load_env()

    for key in REQUIRED:
        if not get(key):
            errors.append(f"{key} is not set")

    if errors:
        return errors

    for key, default in (
        ("DATABASE_PATH", "data/synthetic.db"),
        ("DATA_DIR", "data"),
        ("METRICS_DIR", "data/metrics"),
        ("GRAPHS_DIR", "data/graphs"),
        ("MODELS_DIR", "data/models"),
    ):
        try:
            path = resolve_path(key, default)
            path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            errors.append(f"{key}: {exc}")

    config_file = project_root() / "domain_config.yaml"
    if not config_file.is_file():
        errors.append(f"domain_config.yaml not found at {config_file}")

    return errors


def check_git_env() -> list[str]:
    """BUG-11.02 — .env must not be tracked in git."""
    root = project_root()
    if not (root / ".git").exists():
        return []
    result = subprocess.run(
        ["git", "ls-files", ".env"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    tracked = result.stdout.strip()
    if tracked:
        return [f".env is tracked in git: {tracked}"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Check .env configuration")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--check-git", action="store_true", help="Verify .env is not tracked in git")
    args = parser.parse_args()

    errors = check_config()
    if args.check_git:
        errors.extend(check_git_env())
    if args.verbose and not errors:
        print("Local-only project — no API keys required")
        print(f"Project root: {project_root()}")

    if errors:
        print("Env check FAILED:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("Env check PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

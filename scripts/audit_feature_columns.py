"""Pre-bugs helper — detect forbidden generator columns in exports (BUG-1.07, BUG-10.01)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.env import load_env, resolve_path

# Hidden generator columns — must never appear in metrics/model exports (dataschema.md §13).
FORBIDDEN_EXACT = frozenset(
    {
        "activity_propensity",
        "taste_cluster_id",
        "popularity_score",
        "quality_score",
        "specialization_cluster_id",
        "had_active_connection_at_start",
        "rule_id",
        "rule_type",
        "source_node_id",
        "target_selector",
        "propagation_delay_days",
        "effect_size",
        "decay_rate",
        "max_hops",
        "condition_json",
    }
)

FORBIDDEN_PATTERNS = (
    re.compile(r"^_gen_", re.I),
    re.compile(r"planted_influence", re.I),
    re.compile(r"influence_rule", re.I),
)


def is_forbidden_column(name: str) -> bool:
    if name in FORBIDDEN_EXACT:
        return True
    return any(pattern.search(name) for pattern in FORBIDDEN_PATTERNS)


def _scan_tabular_file(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        import pandas as pd
    except ImportError:
        return [f"{path}: pandas required to audit columns"]

    try:
        if path.suffix == ".parquet":
            columns = list(pd.read_parquet(path).columns)
        elif path.suffix in {".csv", ".tsv"}:
            columns = list(pd.read_csv(path, nrows=0).columns)
        else:
            return []
    except Exception as exc:
        return [f"{path}: failed to read ({exc})"]

    for col in columns:
        if is_forbidden_column(str(col)):
            errors.append(f"Forbidden column '{col}' in {path}")
    return errors


def scan_export_dirs(*dirs: Path, phase2: bool = False) -> list[str]:
    errors: list[str] = []
    extensions = {".parquet", ".csv", ".tsv"}

    for directory in dirs:
        if not directory.is_dir():
            if phase2 and "models" in directory.parts:
                errors.append(f"Models directory missing: {directory}")
            continue

        files = [p for p in directory.rglob("*") if p.is_file() and p.suffix in extensions]
        for path in files:
            errors.extend(_scan_tabular_file(path))

        if phase2 and directory.name == "models":
            manifest = directory / "pyg" / "manifest.json"
            if manifest.is_file():
                import json

                data = json.loads(manifest.read_text(encoding="utf-8"))
                for name in data.get("feature_names", []):
                    if is_forbidden_column(str(name)):
                        errors.append(f"Forbidden PyG feature '{name}' in {manifest}")
            elif not files and not (directory / "pyg").exists():
                errors.append(f"No model export files found in {directory}")

    return errors


def audit(*, phase2: bool = False) -> list[str]:
    load_env()
    metrics_dir = resolve_path("METRICS_DIR", "data/metrics")
    models_dir = resolve_path("MODELS_DIR", "data/models")
    return scan_export_dirs(metrics_dir, models_dir, phase2=phase2)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit exports for forbidden generator columns")
    parser.add_argument("--phase2", action="store_true", help="Also require model export directory")
    args = parser.parse_args()

    errors = audit(phase2=args.phase2)
    if errors:
        print("Feature column audit FAILED:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("Feature column audit PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Phase 2 GNN training CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.env import load_env


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser(description="Train Phase 2 PyG models")
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    try:
        from analytics.pyg.convert import export_all_layers
        from analytics.pyg.train import TrainConfig, train_all_models

        print("Exporting PyG graphs...")
        export_all_layers()
        report = train_all_models(TrainConfig(epochs=args.epochs, seed=args.seed))
        print("\nTraining complete.")
        for name, metrics in report.models.items():
            print(f"  {name}: {metrics}")

        from scripts.check_influence_recovery import check_recovery

        errors, warnings = check_recovery()
        for warn in warnings:
            print(f"  WARNING: {warn}")
        if errors:
            print("\nInfluence recovery check FAILED:", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            return 1
        print("\nInfluence recovery check PASSED")
        return 0
    except ImportError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Training FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

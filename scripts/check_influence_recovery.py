"""Verify influence recovery beats baseline (Phase 2.6, BUG-10.01)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analytics.pyg.predictions import load_predictions, load_training_metadata, predictions_path
from config.env import load_env

OVERFIT_THRESHOLD = 0.99


def check_recovery(
    *,
    min_recovery: float = 0.0,
    require_predictions: bool = True,
    strict_overfitting: bool = False,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    meta = load_training_metadata()
    models = meta.get("models", {})
    influence = models.get("influence_propagation")

    if not influence:
        return ["influence_propagation metrics missing — run: python scripts/run.py train-models"], warnings

    accuracy = float(influence.get("accuracy", 0.0))
    baseline = float(influence.get("baseline", 0.0))
    recovery = float(influence.get("recovery_rate", max(0.0, accuracy - baseline)))

    print(f"Influence propagation accuracy: {accuracy:.4f}")
    print(f"Baseline: {baseline:.4f}")
    print(f"Recovery rate (accuracy - baseline): {recovery:.4f}")

    if accuracy <= baseline:
        errors.append(f"accuracy {accuracy:.4f} not above baseline {baseline:.4f}")
    if recovery <= min_recovery:
        errors.append(f"recovery_rate {recovery:.4f} below minimum {min_recovery:.4f}")

    for name, metrics in models.items():
        acc = float(metrics.get("accuracy", 0.0))
        if acc > OVERFIT_THRESHOLD:
            msg = f"{name} accuracy {acc:.4f} exceeds {OVERFIT_THRESHOLD} — review for overfitting"
            if strict_overfitting:
                errors.append(msg)
            else:
                warnings.append(msg)

    adoption = models.get("combined_adoption", {})
    if adoption:
        acc = float(adoption.get("accuracy", 0.0))
        base = float(adoption.get("baseline", 0.5))
        src = adoption.get("label_source", "unknown")
        print(f"Combined adoption accuracy: {acc:.4f} (baseline {base:.4f}, labels={src})")
        if base < 1.0 and acc <= base:
            errors.append(f"adoption accuracy {acc:.4f} not above baseline {base:.4f}")

    churn = models.get("churn_cascade", {})
    if churn:
        acc = float(churn.get("accuracy", 0.0))
        base = float(churn.get("baseline", 0.5))
        pos = int(churn.get("test_positives", 0))
        neg = int(churn.get("test_negatives", 0))
        print(f"Churn cascade accuracy: {acc:.4f} (baseline {base:.4f}, test {pos} exposed / {neg} not, labels={churn.get('label_source', 'unknown')})")
        if acc <= base:
            errors.append(f"churn accuracy {acc:.4f} not above baseline {base:.4f}")

    if require_predictions:
        pred_path = predictions_path()
        if not pred_path.is_file():
            errors.append(f"predictions file missing: {pred_path}")
        else:
            preds = load_predictions()
            if preds.empty:
                errors.append("predictions.parquet is empty")
            elif "confidence" not in preds.columns or preds["confidence"].isna().all():
                errors.append("predictions missing confidence scores")
            else:
                print(f"Cached predictions: {len(preds)} rows, types: {sorted(preds['prediction_type'].unique())}")

    return errors, warnings


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser(description="Check Phase 2 influence recovery metrics")
    parser.add_argument("--min-recovery", type=float, default=0.0, help="Minimum recovery_rate above baseline")
    parser.add_argument("--no-predictions", action="store_true", help="Skip predictions file check")
    parser.add_argument("--strict-overfitting", action="store_true", help="Fail on accuracy > 99%")
    args = parser.parse_args()

    errors, warnings = check_recovery(
        min_recovery=args.min_recovery,
        require_predictions=not args.no_predictions,
        strict_overfitting=args.strict_overfitting,
    )
    if warnings:
        print("\nWarnings:")
        for warn in warnings:
            print(f"  - {warn}")

    if errors:
        print("\nInfluence recovery check FAILED:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("\nInfluence recovery check PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

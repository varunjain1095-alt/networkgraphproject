"""Per-layer signal breakdown for combined adoption explainability (evals.md Phase 2)."""

from __future__ import annotations

import pandas as pd


LAYER_LABELS = (
    ("layer1", "Layer 1 — Relationships"),
    ("layer2", "Layer 2 — Shared activity"),
    ("layer3", "Layer 3 — User–item"),
    ("layer4", "Layer 4 — Influence"),
)


def _metric(row: pd.Series, *candidates: str, default: float = 0.0) -> float:
    for name in candidates:
        if name in row.index and pd.notna(row[name]):
            return max(float(row[name]), 0.0)
    return default


def compute_layer_contributions(
    ranked_row: pd.Series,
    predictions: pd.DataFrame,
    user_id: str,
) -> list[tuple[str, float]]:
    """Return normalized contribution weights across the four graph layers."""
    adoption_score = 0.0
    if not predictions.empty:
        user_adopt = predictions[
            (predictions["user_id"] == user_id) & (predictions["prediction_type"] == "adoption")
        ]
        if not user_adopt.empty:
            adoption_score = float(user_adopt["score"].max())

    raw = {
        "Layer 1 — Relationships": _metric(
            ranked_row, "layer1_eigenvector", "layer1_betweenness", "layer1_degree"
        ),
        "Layer 2 — Shared activity": min(
            _metric(ranked_row, "layer2_degree", "layer2_eigenvector") / 50.0, 1.0
        ),
        "Layer 3 — User–item": adoption_score or min(_metric(ranked_row, "layer3_degree") / 20.0, 1.0),
        "Layer 4 — Influence": _metric(
            ranked_row, "layer4_eigenvector", "layer4_degree", "layer4_betweenness"
        ),
    }
    total = sum(raw.values())
    if total <= 0:
        return [(label, 0.25) for _, label in LAYER_LABELS]
    return sorted(((label, weight / total) for label, weight in raw.items()), key=lambda x: -x[1])


def format_contribution_breakdown(contributions: list[tuple[str, float]]) -> str:
    parts = [f"{label}: {share:.0%}" for label, share in contributions if share > 0]
    return " · ".join(parts) if parts else "Insufficient signal for layer breakdown."

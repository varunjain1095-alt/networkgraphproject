"""Load cached PyG predictions for use cases and dashboard (Phase 2.7)."""

from __future__ import annotations

from functools import lru_cache

import pandas as pd

from analytics.pyg.predictions import load_predictions


@lru_cache(maxsize=1)
def _predictions() -> pd.DataFrame:
    return load_predictions()


def get_user_predictions(user_id: str, prediction_type: str | None = None) -> pd.DataFrame:
    df = _predictions()
    if df.empty:
        return df
    subset = df[df["user_id"] == user_id]
    if prediction_type:
        subset = subset[subset["prediction_type"] == prediction_type]
    return subset


def prediction_score(user_id: str, prediction_type: str) -> float | None:
    subset = get_user_predictions(user_id, prediction_type)
    if subset.empty:
        return None
    return float(subset["score"].max())


def prediction_confidence(user_id: str, prediction_type: str) -> float | None:
    subset = get_user_predictions(user_id, prediction_type)
    if subset.empty:
        return None
    row = subset.loc[subset["score"].idxmax()]
    return float(row["confidence"])


def forward_adoption_score(user_id: str) -> float | None:
    return prediction_score(user_id, "adoption")

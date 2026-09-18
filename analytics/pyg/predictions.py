"""Cache and load model predictions (Phase 2.7)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from config.env import resolve_path

PREDICTION_COLUMNS = [
    "user_id",
    "prediction_type",
    "target_id",
    "score",
    "confidence",
    "model_name",
    "computed_at",
]


def predictions_path(base: Path | None = None) -> Path:
    root = base or resolve_path("MODELS_DIR", "data/models")
    return root / "predictions.parquet"


def metadata_path(base: Path | None = None) -> Path:
    root = base or resolve_path("MODELS_DIR", "data/models")
    return root / "training_metadata.json"


def save_predictions(rows: list[dict], base: Path | None = None) -> Path:
    out = predictions_path(base)
    out.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=PREDICTION_COLUMNS)
    if out.is_file():
        existing = pd.read_parquet(out)
        keep = existing[~existing["model_name"].isin(df["model_name"].unique())]
        df = pd.concat([keep, df], ignore_index=True)
    df.to_parquet(out, index=False)
    return out


def load_predictions(base: Path | None = None) -> pd.DataFrame:
    path = predictions_path(base)
    if not path.is_file():
        return pd.DataFrame(columns=PREDICTION_COLUMNS)
    return pd.read_parquet(path)


def predictions_for_user(user_id: str, base: Path | None = None) -> pd.DataFrame:
    df = load_predictions(base)
    if df.empty:
        return df
    return df[df["user_id"] == user_id]


def save_training_metadata(meta: dict, base: Path | None = None) -> Path:
    path = metadata_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    meta["computed_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return path


def load_training_metadata(base: Path | None = None) -> dict:
    path = metadata_path(base)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))

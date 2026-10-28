"""PyG analytics package (Phase 2)."""

from __future__ import annotations

from analytics.pyg.features import ALLOWED_METRIC_NAMES, FEATURE_NAMES, load_metric_features
from analytics.pyg.predictions import load_predictions, load_training_metadata, save_predictions

__all__ = [
    "ALLOWED_METRIC_NAMES",
    "FEATURE_NAMES",
    "GraphSplit",
    "HAS_PYG",
    "TrainConfig",
    "TrainReport",
    "community_holdout_split",
    "convert_layer",
    "count_cross_split_edges",
    "export_all_layers",
    "load_metric_features",
    "load_predictions",
    "load_pyg_layer",
    "load_training_metadata",
    "networkx_to_pyg",
    "save_predictions",
    "train_all_models",
]


def __getattr__(name: str):
    if name in ("GraphSplit", "community_holdout_split", "count_cross_split_edges"):
        from analytics.pyg import split

        return getattr(split, name)
    if name in ("HAS_PYG", "convert_layer", "export_all_layers", "load_pyg_layer", "networkx_to_pyg"):
        from analytics.pyg import convert

        return getattr(convert, name)
    if name in ("TrainConfig", "TrainReport", "train_all_models"):
        from analytics.pyg import train

        return getattr(train, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

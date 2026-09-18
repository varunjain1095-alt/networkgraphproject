"""Save and load graph pickles."""

from __future__ import annotations

import json
import pickle
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import networkx as nx

from config.env import resolve_path
from graphs.settings import LAYER_FILES


def graphs_dir() -> Path:
    path = resolve_path("GRAPHS_DIR", "data/graphs")
    path.mkdir(parents=True, exist_ok=True)
    return path


def layer_path(name: str) -> Path:
    return graphs_dir() / name


def save_graphs(
    layers: dict[str, nx.Graph],
    projections: dict[str, nx.Graph],
    metadata: dict[str, Any] | None = None,
) -> Path:
    out = graphs_dir()
    if out.exists():
        for f in LAYER_FILES:
            (out / f).unlink(missing_ok=True)

    mapping = {
        "layer1.gpickle": layers["layer1"],
        "layer2.gpickle": layers["layer2"],
        "layer3.gpickle": layers["layer3"],
        "layer4.gpickle": layers["layer4"],
        "projections.gpickle": projections,
    }
    for filename, graph in mapping.items():
        with (out / filename).open("wb") as handle:
            pickle.dump(graph, handle, protocol=pickle.HIGHEST_PROTOCOL)

    meta = metadata or {}
    meta.setdefault("built_at", datetime.now(timezone.utc).isoformat())
    meta["files"] = list(mapping.keys())
    (out / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return out


def load_graph(layer: int | str) -> nx.Graph:
    if isinstance(layer, int):
        filename = f"layer{layer}.gpickle"
    else:
        filename = layer if layer.endswith(".gpickle") else f"{layer}.gpickle"
    path = layer_path(filename)
    if not path.is_file():
        raise FileNotFoundError(f"Graph cache not found: {path}")
    with path.open("rb") as handle:
        return pickle.load(handle)


def load_projections() -> dict[str, nx.Graph]:
    path = layer_path("projections.gpickle")
    if not path.is_file():
        raise FileNotFoundError(f"Projections cache not found: {path}")
    with path.open("rb") as handle:
        return pickle.load(handle)


def load_metadata() -> dict[str, Any]:
    path = graphs_dir() / "metadata.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def clear_cache() -> None:
    out = graphs_dir()
    if out.is_dir():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

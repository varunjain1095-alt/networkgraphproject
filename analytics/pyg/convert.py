"""NetworkX to PyG conversion (Phase 2.1)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd

from analytics.pyg.features import FEATURE_NAMES, feature_matrix_for_nodes, load_metric_features
from analytics.utils import to_simple_graph
from config.env import resolve_path
from graphs.cache import load_graph
from graphs.db import open_db

try:
    import torch
    from torch_geometric.data import Data

    HAS_PYG = True
except ImportError:
    HAS_PYG = False
    Data = Any  # type: ignore[misc, assignment]


def require_pyg() -> None:
    if not HAS_PYG:
        raise ImportError(
            "PyTorch and torch-geometric are required for Phase 2. "
            "Install with: pip install -r requirements-phase2.txt"
        )


def networkx_to_pyg(
    graph: nx.Graph,
    features: pd.DataFrame,
    *,
    layer: str,
) -> Any:
    """Convert a NetworkX graph to a PyG Data object."""
    require_pyg()
    simple = to_simple_graph(graph)
    ordered = [str(n) for n in simple.nodes()]

    index = {node: i for i, node in enumerate(ordered)}
    edges: list[list[int]] = []
    weights: list[float] = []
    for u, v, data in simple.edges(data=True):
        su, sv = str(u), str(v)
        if su not in index or sv not in index:
            continue
        i, j = index[su], index[sv]
        w = float(data.get("weight", data.get("session_count", 1.0)) if isinstance(data, dict) else 1.0)
        edges.append([i, j])
        edges.append([j, i])
        weights.extend([w, w])

    if edges:
        edge_index = torch.tensor(edges, dtype=torch.long).t().contiguous()
        edge_attr = torch.tensor(weights, dtype=torch.float).view(-1, 1)
    else:
        edge_index = torch.zeros((2, 0), dtype=torch.long)
        edge_attr = torch.zeros((0, 1), dtype=torch.float)

    x = torch.tensor(feature_matrix_for_nodes(features, ordered), dtype=torch.float)

    data = Data(x=x, edge_index=edge_index, edge_attr=edge_attr)
    data.node_ids = ordered
    data.layer = layer
    data.num_nodes = len(ordered)
    return data


def convert_layer(layer: int, conn: sqlite3.Connection | None = None) -> Any:
    """Load cached NetworkX graph and export PyG Data for one layer."""
    own_conn = conn is None
    conn = conn or open_db()
    try:
        graph = load_graph(layer)
        layer_name = f"layer{layer}"
        features = load_metric_features(conn, layer_name)
        return networkx_to_pyg(graph, features, layer=layer_name)
    finally:
        if own_conn:
            conn.close()


def export_all_layers(output_dir: Path | None = None) -> Path:
    """Export all four layer graphs to cached .pt files."""
    require_pyg()
    out = output_dir or resolve_path("MODELS_DIR", "data/models") / "pyg"
    out.mkdir(parents=True, exist_ok=True)

    conn = open_db()
    manifest: dict[str, Any] = {"layers": {}, "feature_names": list(FEATURE_NAMES)}
    try:
        for layer in (1, 2, 3, 4):
            data = convert_layer(layer, conn)
            path = out / f"layer{layer}.pt"
            torch.save(data, path)
            manifest["layers"][f"layer{layer}"] = {
                "path": str(path.name),
                "num_nodes": int(data.num_nodes),
                "num_edges": int(data.edge_index.shape[1]),
                "num_features": int(data.x.shape[1]) if data.x.numel() else 0,
            }
            print(f"  layer{layer}: {data.num_nodes} nodes, {data.edge_index.shape[1]} edges")
    finally:
        conn.close()

    meta_path = out / "manifest.json"
    meta_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"PyG export complete: {out}")
    return out


def load_pyg_layer(layer: int, models_dir: Path | None = None) -> Any:
    require_pyg()
    base = models_dir or resolve_path("MODELS_DIR", "data/models") / "pyg"
    path = base / f"layer{layer}.pt"
    if not path.is_file():
        raise FileNotFoundError(f"PyG cache missing: {path}. Run pyg export first.")
    return torch.load(path, weights_only=False)

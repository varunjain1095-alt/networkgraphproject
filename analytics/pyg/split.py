"""Graph-aware train/val/test splits (Phase 2.2, BUG-10.02)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import networkx as nx

try:
    import torch

    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


@dataclass
class GraphSplit:
    train_mask: Any
    val_mask: Any
    test_mask: Any
    train_nodes: list[str]
    val_nodes: list[str]
    test_nodes: list[str]


def _require_torch() -> None:
    if not HAS_TORCH:
        raise ImportError("PyTorch required for graph splits")


def community_holdout_split(
    graph: nx.Graph,
    community_map: dict[str, int],
    *,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    seed: int = 42,
) -> GraphSplit:
    """Assign whole communities to splits to reduce neighbor leakage."""
    _require_torch()
    import random

    rng = random.Random(seed)
    communities: dict[int, list[str]] = {}
    for node in graph.nodes():
        comm = int(community_map.get(str(node), -1))
        communities.setdefault(comm, []).append(str(node))

    comm_ids = list(communities.keys())
    rng.shuffle(comm_ids)
    n = len(comm_ids)
    n_train = max(1, int(n * train_ratio))
    n_val = max(0, int(n * val_ratio))
    train_comms = set(comm_ids[:n_train])
    val_comms = set(comm_ids[n_train : n_train + n_val])
    test_comms = set(comm_ids[n_train + n_val :]) or {comm_ids[-1]}

    train_nodes = [n for c in train_comms for n in communities[c]]
    val_nodes = [n for c in val_comms for n in communities[c]]
    test_nodes = [n for c in test_comms for n in communities[c]]

    node_list = [str(n) for n in graph.nodes()]
    index = {n: i for i, n in enumerate(node_list)}
    train_set, val_set, test_set = set(train_nodes), set(val_nodes), set(test_nodes)

    train_mask = torch.tensor([n in train_set for n in node_list], dtype=torch.bool)
    val_mask = torch.tensor([n in val_set for n in node_list], dtype=torch.bool)
    test_mask = torch.tensor([n in test_set for n in node_list], dtype=torch.bool)

    return GraphSplit(
        train_mask=train_mask,
        val_mask=val_mask,
        test_mask=test_mask,
        train_nodes=train_nodes,
        val_nodes=val_nodes,
        test_nodes=test_nodes,
    )


def count_cross_split_edges(graph: nx.Graph, split: GraphSplit, node_list: list[str]) -> int:
    """Count edges with one endpoint in test and one outside test."""
    test_set = set(split.test_nodes)
    cross = 0
    for u, v in graph.edges():
        su, sv = str(u), str(v)
        if (su in test_set) ^ (sv in test_set):
            cross += 1
    return cross


def load_community_map(conn, graph_layer: str = "layer1") -> dict[str, int]:
    import sqlite3

    rows = conn.execute(
        """
        SELECT node_id, community_id FROM node_metrics
        WHERE graph_layer = ? AND community_id IS NOT NULL
        """,
        (graph_layer,),
    ).fetchall()
    return {str(r[0]): int(r[1]) for r in rows if r[1] is not None}

"""Ego network extraction with display cap."""

from __future__ import annotations

from typing import Any

import networkx as nx

from graphs.settings import EGO_NETWORK_CAP


def _neighbor_weight(graph: nx.Graph, center: str, neighbor: str) -> float:
    data = graph.get_edge_data(center, neighbor)
    if not data:
        return 0.0
    if isinstance(data, dict) and 0 in data:
        data = data[0]
    if isinstance(data, dict):
        return float(data.get("weight", data.get("session_count", 1)))
    return 1.0


def extract_ego_network(
    graph: nx.Graph,
    center: str,
    radius: int = 1,
    cap: int = EGO_NETWORK_CAP,
) -> tuple[nx.Graph, dict[str, Any]]:
    """Return ego subgraph and metadata including shown/total counts."""
    if center not in graph:
        empty = nx.Graph()
        empty.add_node(center, node_type="user", missing=True)
        return empty, {"center": center, "shown": 1, "total": 1, "truncated": False, "missing": True}

    if radius != 1:
        nodes = nx.ego_graph(graph, center, radius=radius).nodes()
    else:
        nodes = {center, *graph.neighbors(center)}

    if center not in nodes:
        nodes.add(center)

    neighbors = [n for n in nodes if n != center]
    total = len(neighbors) + 1
    max_neighbors = max(0, cap - 1)  # cap includes center node
    truncated = len(neighbors) > max_neighbors

    if truncated:
        neighbors = sorted(
            neighbors,
            key=lambda n: _neighbor_weight(graph, center, n),
            reverse=True,
        )[:max_neighbors]
        nodes = {center, *neighbors}

    subgraph = graph.subgraph(nodes).copy()
    meta = {
        "center": center,
        "shown": subgraph.number_of_nodes(),
        "total": total,
        "truncated": truncated,
        "missing": False,
    }
    if truncated:
        meta["message"] = f"Showing {len(neighbors)} of {total - 1} connections"
    return subgraph, meta

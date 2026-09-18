"""Shared helpers for NetworkX analytics."""

from __future__ import annotations

import math
from typing import Iterable

import networkx as nx
import numpy as np


def to_simple_graph(graph: nx.Graph, weight: str = "weight") -> nx.Graph:
    """Collapse Multi(Di)Graph to simple weighted Graph for metric algorithms."""
    if isinstance(graph, (nx.MultiGraph, nx.MultiDiGraph)):
        simple = nx.Graph()
        for u, v, data in graph.edges(data=True):
            w = float(data.get(weight, 1.0))
            if simple.has_edge(u, v):
                simple[u][v][weight] = simple[u][v].get(weight, 0) + w
            else:
                simple.add_edge(u, v, **{weight: w})
        for node, attrs in graph.nodes(data=True):
            simple.add_node(node, **attrs)
        return simple
    if isinstance(graph, nx.DiGraph):
        undirected = nx.Graph()
        undirected.add_nodes_from((n, dict(d)) for n, d in graph.nodes(data=True))
        for u, v, data in graph.edges(data=True):
            w = float(data.get(weight, 1.0))
            if undirected.has_edge(u, v):
                undirected[u][v][weight] = max(undirected[u][v].get(weight, 0), w)
            else:
                undirected.add_edge(u, v, **{weight: w})
        return undirected
    return graph


def normalize_scores(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return scores
    values = np.array(list(scores.values()), dtype=float)
    if len(values) == 0:
        return scores
    min_v, max_v = float(values.min()), float(values.max())
    if math.isclose(min_v, max_v):
        return {k: 0.0 for k in scores}
    return {k: (v - min_v) / (max_v - min_v) for k, v in scores.items()}


def user_nodes(graph: nx.Graph) -> list[str]:
    return [n for n, d in graph.nodes(data=True) if d.get("node_type", "user") == "user"]


def safe_eigenvector(graph: nx.Graph, weight: str = "weight", max_iter: int = 500) -> dict[str, float]:
    if graph.number_of_edges() == 0:
        return {n: 0.0 for n in graph.nodes()}
    try:
        return nx.eigenvector_centrality(graph, max_iter=max_iter, weight=weight)
    except nx.PowerIterationFailedConvergence:
        return {n: 0.0 for n in graph.nodes()}


def safe_betweenness(
    graph: nx.Graph,
    weight: str = "weight",
    k: int | None = None,
) -> dict[str, float]:
    if graph.number_of_nodes() <= 1:
        return {n: 0.0 for n in graph.nodes()}
    sample = k
    if sample and graph.number_of_nodes() <= sample:
        sample = None
    return nx.betweenness_centrality(graph, k=sample, weight=weight, normalized=True)


def louvain_partition(graph: nx.Graph, seed: int, weight: str = "weight") -> dict[str, int]:
    from networkx.algorithms import community

    if graph.number_of_nodes() == 0:
        return {}
    simple = to_simple_graph(graph, weight=weight)
    if simple.number_of_edges() == 0:
        return {n: i for i, n in enumerate(simple.nodes())}

    communities = community.louvain_communities(simple, weight=weight, seed=seed)
    partition: dict[str, int] = {}
    for idx, comm in enumerate(communities):
        for node in comm:
            partition[node] = idx
    for node in simple.nodes():
        partition.setdefault(node, len(communities))
    return partition


def iter_node_metric_rows(
    node_id: str,
    node_type: str,
    graph_layer: str,
    metrics: dict[str, float],
    community_id: int | None,
    computed_at: str,
) -> Iterable[tuple]:
    for name, value in metrics.items():
        if value is None or (isinstance(value, float) and math.isnan(value)):
            value = 0.0
        yield (node_id, node_type, graph_layer, name, float(value), community_id, computed_at)

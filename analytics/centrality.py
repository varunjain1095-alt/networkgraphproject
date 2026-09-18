"""Compute centrality and degree metrics."""

from __future__ import annotations

import networkx as nx

from analytics.utils import safe_betweenness, safe_eigenvector, to_simple_graph, user_nodes


def compute_layer_centralities(
    graph: nx.Graph,
    graph_layer: str,
    seed: int,
    betweenness_k: int | None = 500,
) -> dict[str, dict[str, float]]:
    """Return per-node metrics dict keyed by node_id."""
    simple = to_simple_graph(graph)
    nodes = list(simple.nodes())
    if not nodes:
        return {}

    degree = dict(simple.degree(weight="weight"))
    between = safe_betweenness(simple, k=betweenness_k)
    eigen = safe_eigenvector(simple)

    results: dict[str, dict[str, float]] = {}
    for node in nodes:
        node_type = simple.nodes[node].get("node_type", "user")
        metrics: dict[str, float] = {"degree": float(degree.get(node, 0))}
        if graph_layer in ("layer1", "layer2", "layer4") and node_type == "user":
            metrics["betweenness"] = float(between.get(node, 0.0))
            metrics["eigenvector"] = float(eigen.get(node, 0.0))
        elif graph_layer == "layer3":
            metrics["degree"] = float(degree.get(node, 0))
        results[node] = {"node_type": node_type, "metrics": metrics}
    return results


def layer4_user_social_graph(graph: nx.MultiDiGraph) -> nx.Graph:
    """User-user edges from validation and follow relationships on layer 4."""
    g = nx.Graph()
    for node, data in graph.nodes(data=True):
        if data.get("node_type") == "user":
            g.add_node(node, **data)

    contrib_author: dict[str, str] = {}
    for node, data in graph.nodes(data=True):
        if data.get("node_type") == "contribution":
            contrib_author[node] = data.get("author_id")

    for u, v, data in graph.edges(data=True):
        et = data.get("edge_type")
        if et == "validated" and v in contrib_author:
            author = contrib_author[v]
            if u != author:
                g.add_edge(u, author, weight=g.get_edge_data(u, author, default={}).get("weight", 0) + 1)
        elif et == "follows":
            # source nodes skipped — only user-user via co-validation for now
            pass

    return g

"""Cytoscape graph view helpers."""

from __future__ import annotations

import networkx as nx

from graphs.ego import extract_ego_network

LAYER_LAYOUT_OVERRIDES = {
    "layer2": {
        "nodeRepulsion": 18000,
        "idealEdgeLength": 140,
        "nodeOverlap": 64,
        "componentSpacing": 180,
    },
    "layer4": {
        "nodeRepulsion": 15000,
        "idealEdgeLength": 125,
        "nodeOverlap": 56,
        "componentSpacing": 170,
    },
}


def layout_for_layer(layer: str, base_layout: dict) -> dict:
    """Return cytoscape layout tuned for layer density."""
    layout = dict(base_layout)
    layout.update(LAYER_LAYOUT_OVERRIDES.get(layer, {}))
    return layout


from collections.abc import Callable


def build_cytoscape_elements(
    graph: nx.Graph,
    center: str | None = None,
    *,
    user_stats: dict[str, dict] | None = None,
) -> list[dict]:
    """Build dash-cytoscape elements list."""
    stats_lookup = user_stats or {}
    elements: list[dict] = []
    for node, data in graph.nodes(data=True):
        label = data.get("display_name") or data.get("title") or data.get("name") or str(node)
        node_type = data.get("node_type", "user")
        node_id = str(node)
        stats = stats_lookup.get(node_id, {})
        elements.append(
            {
                "data": {
                    "id": node_id,
                    "label": str(label)[:24],
                    "display_name": str(label),
                    "node_type": node_type,
                    "rank": stats.get("rank"),
                    "score": stats.get("score"),
                    "percentile": stats.get("percentile"),
                    "layer1_degree": stats.get("layer1_degree"),
                    "layer1_betweenness": stats.get("layer1_betweenness"),
                    "layer2_degree": stats.get("layer2_degree"),
                    "is_center": node_id == center,
                },
                "classes": node_type,
            }
        )
    seen_edges: set[tuple[str, str]] = set()
    for u, v, data in graph.edges(data=True):
        a, b = sorted((str(u), str(v)))
        if (a, b) in seen_edges:
            continue
        seen_edges.add((a, b))
        weight = data.get("weight", data.get("session_count", 1)) if isinstance(data, dict) else 1
        elements.append(
            {
                "data": {
                    "source": str(u),
                    "target": str(v),
                    "weight": float(weight) if weight else 1.0,
                }
            }
        )
    if center and center in graph:
        for el in elements:
            if el["data"].get("id") == center:
                el["classes"] = (el.get("classes", "") + " center").strip()
    return elements


def ego_view(
    base_graph: nx.Graph,
    center: str,
    layer: str,
    *,
    stats_provider: Callable[[list[str]], dict[str, dict]] | None = None,
) -> tuple[list[dict], str, dict]:
    """Return cytoscape elements, caption, and metadata for ego network."""
    if center not in base_graph:
        empty = nx.Graph()
        empty.add_node(center)
        return (
            build_cytoscape_elements(empty, center),
            "No connections found for this node in the selected layer.",
            {"missing": True},
        )

    if layer == "layer3":
        return [], "Ownership patterns use table view. See recommendations below.", {"layer3": True}

    if layer == "layer4":
        simple = base_graph.to_undirected() if hasattr(base_graph, "to_undirected") else base_graph
        ego, meta = extract_ego_network(simple, center, radius=2, cap=80)
    else:
        simple = base_graph
        ego, meta = extract_ego_network(simple, center, radius=1, cap=50)

    stats_lookup: dict[str, dict] = {}
    if stats_provider is not None:
        stats_lookup = stats_provider([str(n) for n in ego.nodes()])
    elements = build_cytoscape_elements(ego, center, user_stats=stats_lookup)
    hint = "Hover nodes for details; click to pin a label."
    if meta.get("shown", 0) <= 1:
        caption = "No connections found for this node."
    elif meta.get("truncated"):
        caption = f"{meta.get('message', 'Network truncated')} · {hint}"
    else:
        caption = f"Showing {meta.get('shown', 0)} nodes · {hint}"
    return elements, caption, meta

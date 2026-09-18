"""Community detection and cluster-level metrics."""

from __future__ import annotations

from datetime import datetime, timezone

import networkx as nx

from analytics.utils import louvain_partition, to_simple_graph


def compute_communities(
    graph: nx.Graph,
    graph_layer: str,
    seed: int,
) -> tuple[dict[str, int], list[dict]]:
    partition = louvain_partition(graph, seed=seed)
    simple = to_simple_graph(graph)
    computed_at = datetime.now(timezone.utc).isoformat()

    by_comm: dict[int, list[str]] = {}
    for node, comm_id in partition.items():
        by_comm.setdefault(comm_id, []).append(node)

    cluster_rows: list[dict] = []
    for comm_id, members in by_comm.items():
        subgraph = simple.subgraph(members)
        n = subgraph.number_of_nodes()
        density = nx.density(subgraph) if n > 1 else 0.0
        reciprocity = None
        if isinstance(graph, (nx.DiGraph, nx.MultiDiGraph)):
            try:
                reciprocity = nx.reciprocity(graph.subgraph(members))
            except Exception:
                reciprocity = 0.0
        cluster_rows.append(
            {
                "community_id": comm_id,
                "graph_layer": graph_layer,
                "node_count": n,
                "density": float(density),
                "reciprocity": reciprocity,
                "avg_exposure_rate": None,
                "computed_at": computed_at,
            }
        )
    return partition, cluster_rows

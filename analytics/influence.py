"""Community-validated influence and pairwise connection strength."""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict

import networkx as nx

from analytics.utils import normalize_scores, to_simple_graph


def compute_community_validated_influence(
    conn: sqlite3.Connection,
    layer4: nx.MultiDiGraph,
    layer1: nx.Graph,
) -> dict[str, float]:
    """Score users by validations received from network neighbors."""
    scores: dict[str, float] = defaultdict(float)
    neighbor_map: dict[str, set[str]] = defaultdict(set)
    simple_l1 = to_simple_graph(layer1)
    for u, v in simple_l1.edges():
        neighbor_map[u].add(v)
        neighbor_map[v].add(u)

    contrib_meta = {
        row["contribution_id"]: (row["user_id"], float(row["quality_score"]))
        for row in conn.execute("SELECT contribution_id, user_id, quality_score FROM contributions")
    }

    for row in conn.execute(
        """
        SELECT c.contribution_id, c.voter_user_id, c.validation_type
        FROM contribution_validation_events c
        """
    ):
        contrib_id = row["contribution_id"]
        voter = row["voter_user_id"]
        if contrib_id not in contrib_meta:
            continue
        author, quality = contrib_meta[contrib_id]
        if voter in neighbor_map.get(author, set()) or voter == author:
            scores[author] += quality * (1.5 if voter in neighbor_map.get(author, set()) else 0.5)

    for user_id in user_nodes(layer4):
        scores.setdefault(user_id, 0.0)

    return normalize_scores(dict(scores))


def user_nodes(graph: nx.Graph) -> list[str]:
    return [n for n, d in graph.nodes(data=True) if d.get("node_type") == "user"]


def compute_pairwise_strength(
    conn: sqlite3.Connection,
    layer1: nx.Graph,
    layer2: nx.Graph,
) -> list[dict]:
    """Composite relationship + activity strength for contamination detection."""
    rel_strength: dict[tuple[str, str], float] = {}
    simple_l1 = to_simple_graph(layer1)
    max_rel = 0.0
    for u, v, data in simple_l1.edges(data=True):
        pair = (min(u, v), max(u, v))
        rel_strength[pair] = rel_strength.get(pair, 0.0) + 1.0
        max_rel = max(max_rel, rel_strength[pair])

    act_strength: dict[tuple[str, str], float] = {}
    max_act = 0.0
    for u, v, data in layer2.edges(data=True):
        pair = (min(u, v), max(u, v))
        w = float(data.get("weight", 1.0))
        act_strength[pair] = max(act_strength.get(pair, 0.0), w)
        max_act = max(max_act, w)

    exp_variants: dict[str, dict[str, str]] = defaultdict(dict)
    for row in conn.execute(
        "SELECT user_id, experiment_id, variant FROM feature_exposure_log"
    ):
        exp_variants[row["user_id"]][row["experiment_id"]] = row["variant"]

    pairs = set(rel_strength) | set(act_strength)
    rows = []
    for a, b in pairs:
        rs = rel_strength.get((a, b), 0.0) / max_rel if max_rel else 0.0
        ac = act_strength.get((a, b), 0.0) / max_act if max_act else 0.0
        combined = 0.6 * rs + 0.4 * ac
        shared_conflicts = []
        for exp_id, var_a in exp_variants.get(a, {}).items():
            var_b = exp_variants.get(b, {}).get(exp_id)
            if var_b and var_a != var_b:
                shared_conflicts.append(exp_id)
        rows.append(
            {
                "user_id_a": a,
                "user_id_b": b,
                "relationship_strength": rs,
                "activity_strength": ac,
                "combined_strength": combined,
                "shared_experiment_ids": json.dumps(shared_conflicts),
            }
        )
    return rows

"""Build NetworkX graphs for all four layers."""

from __future__ import annotations

import sqlite3

import networkx as nx


def build_layer1(conn: sqlite3.Connection) -> nx.MultiDiGraph:
    """Users + typed relationship edges. All users included even if isolated."""
    g = nx.MultiDiGraph(name="layer1_relationships")

    for row in conn.execute("SELECT user_id, organization_id, display_name FROM users"):
        g.add_node(row["user_id"], node_type="user", organization_id=row["organization_id"], display_name=row["display_name"])

    for row in conn.execute(
        """
        SELECT user_id_a, user_id_b, relationship_type, connection_date, organization_scope
        FROM relationship_edges
        """
    ):
        attrs = {
            "relationship_type": row["relationship_type"],
            "connection_date": row["connection_date"],
            "organization_scope": row["organization_scope"],
        }
        u, v = row["user_id_a"], row["user_id_b"]
        g.add_edge(u, v, **attrs)
        if row["relationship_type"] in ("friend", "collaborate"):
            g.add_edge(v, u, **attrs)

    return g


def build_layer2(conn: sqlite3.Connection) -> nx.Graph:
    """Weighted shared-activity graph derived from session co-participation."""
    g = nx.Graph(name="layer2_shared_activity")

    for row in conn.execute("SELECT user_id FROM users"):
        g.add_node(row["user_id"], node_type="user")

    rel_pairs = {
        (min(r["user_id_a"], r["user_id_b"]), max(r["user_id_a"], r["user_id_b"]))
        for r in conn.execute("SELECT user_id_a, user_id_b FROM relationship_edges")
    }

    query = """
        SELECT
            CASE WHEN p1.user_id < p2.user_id THEN p1.user_id ELSE p2.user_id END AS user_id_a,
            CASE WHEN p1.user_id < p2.user_id THEN p2.user_id ELSE p1.user_id END AS user_id_b,
            COUNT(DISTINCT p1.session_id) AS session_count,
            SUM(s.duration_seconds) AS total_duration
        FROM activity_session_participants p1
        JOIN activity_session_participants p2
          ON p1.session_id = p2.session_id AND p1.user_id < p2.user_id
        JOIN activity_sessions s ON s.session_id = p1.session_id
        GROUP BY 1, 2
    """
    for row in conn.execute(query):
        u, v = row["user_id_a"], row["user_id_b"]
        sessions = int(row["session_count"])
        duration = int(row["total_duration"] or 0)
        weight = sessions + duration / 3600.0
        pair = (u, v)
        g.add_edge(
            u,
            v,
            weight=weight,
            session_count=sessions,
            total_duration=duration,
            has_relationship_edge=1 if pair in rel_pairs else 0,
        )

    return g


def build_layer3(conn: sqlite3.Connection) -> nx.Graph:
    """Bipartite user-item graph from interactions."""
    g = nx.Graph(name="layer3_user_item")

    for row in conn.execute("SELECT user_id, display_name FROM users"):
        g.add_node(row["user_id"], node_type="user", bipartite=0, display_name=row["display_name"])

    for row in conn.execute("SELECT item_id, title FROM items"):
        g.add_node(row["item_id"], node_type="item", bipartite=1, title=row["title"])

    for row in conn.execute(
        """
        SELECT user_id, item_id, interaction_type, interaction_date, usage_total, transaction_value
        FROM user_item_interactions
        """
    ):
        g.add_edge(
            row["user_id"],
            row["item_id"],
            interaction_type=row["interaction_type"],
            interaction_date=row["interaction_date"],
            usage_total=row["usage_total"],
            transaction_value=row["transaction_value"],
        )

    return g


def build_layer4(conn: sqlite3.Connection) -> nx.MultiDiGraph:
    """Users, sources, contributions, and influence edges."""
    g = nx.MultiDiGraph(name="layer4_influence")

    for row in conn.execute("SELECT user_id, display_name FROM users"):
        g.add_node(row["user_id"], node_type="user", display_name=row["display_name"])

    for row in conn.execute("SELECT source_id, name, source_type FROM trusted_sources"):
        g.add_node(row["source_id"], node_type="source", name=row["name"], source_type=row["source_type"])

    for row in conn.execute(
        "SELECT contribution_id, user_id, item_id, quality_score, contribution_timestamp FROM contributions"
    ):
        g.add_node(
            row["contribution_id"],
            node_type="contribution",
            author_id=row["user_id"],
            item_id=row["item_id"],
            quality_score=row["quality_score"],
        )
        g.add_edge(row["user_id"], row["contribution_id"], edge_type="authored", timestamp=row["contribution_timestamp"])

    for row in conn.execute("SELECT item_id, title FROM items"):
        if not g.has_node(row["item_id"]):
            g.add_node(row["item_id"], node_type="item", title=row["title"])

    for row in conn.execute("SELECT user_id, source_id, follow_date FROM source_follows"):
        g.add_edge(row["user_id"], row["source_id"], edge_type="follows", timestamp=row["follow_date"])

    for row in conn.execute(
        """
        SELECT contribution_id, voter_user_id, validation_type, validation_timestamp
        FROM contribution_validation_events
        """
    ):
        g.add_edge(
            row["voter_user_id"],
            row["contribution_id"],
            edge_type="validated",
            validation_type=row["validation_type"],
            timestamp=row["validation_timestamp"],
        )

    for row in conn.execute(
        "SELECT source_id, item_id, recommendation_date FROM source_recommendations"
    ):
        g.add_edge(
            row["source_id"],
            row["item_id"],
            edge_type="recommends",
            timestamp=row["recommendation_date"],
        )

    return g

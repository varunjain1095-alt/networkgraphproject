"""Derived item-item and user-user projections from Layer 3."""

from __future__ import annotations

import sqlite3

import networkx as nx

from graphs.settings import MIN_SHARED_USERS


def build_projections(conn: sqlite3.Connection, min_shared: int = MIN_SHARED_USERS) -> dict[str, nx.Graph]:
    item_item = nx.Graph(name="item_item_projection")
    user_user = nx.Graph(name="user_user_projection")

    item_query = """
        SELECT
            i1.item_id AS item_a,
            i2.item_id AS item_b,
            COUNT(DISTINCT i1.user_id) AS shared_users
        FROM user_item_interactions i1
        JOIN user_item_interactions i2
          ON i1.user_id = i2.user_id AND i1.item_id < i2.item_id
        GROUP BY i1.item_id, i2.item_id
        HAVING shared_users >= ?
    """
    for row in conn.execute(item_query, (min_shared,)):
        item_item.add_edge(
            row["item_a"],
            row["item_b"],
            shared_user_count=int(row["shared_users"]),
        )

    user_query = """
        SELECT
            CASE WHEN i1.user_id < i2.user_id THEN i1.user_id ELSE i2.user_id END AS user_a,
            CASE WHEN i1.user_id < i2.user_id THEN i2.user_id ELSE i1.user_id END AS user_b,
            COUNT(DISTINCT i1.item_id) AS shared_items
        FROM user_item_interactions i1
        JOIN user_item_interactions i2
          ON i1.item_id = i2.item_id AND i1.user_id < i2.user_id
        GROUP BY 1, 2
        HAVING shared_items >= ?
    """
    for row in conn.execute(user_query, (min_shared,)):
        user_user.add_edge(
            row["user_a"],
            row["user_b"],
            shared_item_count=int(row["shared_items"]),
        )

    return {"item_item": item_item, "user_user": user_user}

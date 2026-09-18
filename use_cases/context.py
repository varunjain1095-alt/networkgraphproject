"""Database + metrics access for use case modules."""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import timedelta
from generator.time_utils import ACTIVE_THRESHOLD_DAYS, simulation_end
from graphs.db import open_db


class UseCaseContext:
    def __init__(self, conn: sqlite3.Connection | None = None):
        self._own_conn = conn is None
        self.conn = conn or open_db()
        self.conn.row_factory = sqlite3.Row
        self._metric_cache: dict[tuple[str, str, str], float] = {}
        self._user_meta: dict[str, dict] | None = None

    def close(self) -> None:
        if self._own_conn:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def user_metric(self, user_id: str, graph_layer: str, metric_name: str, default: float = 0.0) -> float:
        key = (user_id, graph_layer, metric_name)
        if key not in self._metric_cache:
            row = self.conn.execute(
                """
                SELECT metric_value FROM node_metrics
                WHERE node_id = ? AND graph_layer = ? AND metric_name = ?
                """,
                (user_id, graph_layer, metric_name),
            ).fetchone()
            self._metric_cache[key] = float(row["metric_value"]) if row else default
        return self._metric_cache[key]

    def users_with_metric(self, graph_layer: str, metric_name: str) -> list[tuple[str, float]]:
        rows = self.conn.execute(
            """
            SELECT node_id, metric_value FROM node_metrics
            WHERE graph_layer = ? AND metric_name = ? AND node_type = 'user'
            ORDER BY metric_value DESC
            """,
            (graph_layer, metric_name),
        ).fetchall()
        return [(r["node_id"], float(r["metric_value"])) for r in rows]

    def user_meta(self, user_id: str) -> dict:
        if self._user_meta is None:
            self._user_meta = {}
            for row in self.conn.execute(
                "SELECT user_id, display_name, is_active, last_active_date, join_date FROM users"
            ):
                self._user_meta[row["user_id"]] = dict(row)
        return self._user_meta.get(user_id, {})

    def active_user_ids(self) -> set[str]:
        cutoff = simulation_end() - timedelta(days=ACTIVE_THRESHOLD_DAYS)
        cutoff_iso = cutoff.isoformat()
        rows = self.conn.execute(
            """
            SELECT user_id FROM users
            WHERE is_active = 1 AND last_active_date >= ?
            """,
            (cutoff_iso,),
        ).fetchall()
        return {r["user_id"] for r in rows}

    def churned_user_ids(self) -> set[str]:
        rows = self.conn.execute("SELECT user_id FROM churn_events").fetchall()
        return {r["user_id"] for r in rows}

    def neighbors(self, user_id: str) -> set[str]:
        rows = self.conn.execute(
            """
            SELECT user_id_a, user_id_b FROM relationship_edges
            WHERE user_id_a = ? OR user_id_b = ?
            """,
            (user_id, user_id),
        ).fetchall()
        neighbors: set[str] = set()
        for row in rows:
            neighbors.add(row["user_id_b"] if row["user_id_a"] == user_id else row["user_id_a"])
        return neighbors

    def has_active_connection(self, user_id: str) -> bool:
        active = self.active_user_ids()
        return bool(self.neighbors(user_id) & active)

    def cluster_metrics(self, graph_layer: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM cluster_metrics WHERE graph_layer = ? ORDER BY density DESC",
            (graph_layer,),
        ).fetchall()

    def community_members(self, graph_layer: str, community_id: int) -> list[str]:
        rows = self.conn.execute(
            """
            SELECT node_id FROM node_metrics
            WHERE graph_layer = ? AND community_id = ? AND node_type = 'user'
            GROUP BY node_id
            """,
            (graph_layer, community_id),
        ).fetchall()
        return [r["node_id"] for r in rows]

    def pairwise_contamination(self, min_strength: float = 0.2) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT user_id_a, user_id_b, relationship_strength, activity_strength,
                   combined_strength, shared_experiment_ids
            FROM pairwise_connection_strength
            WHERE combined_strength >= ?
            """,
            (min_strength,),
        ).fetchall()
        results = []
        for row in rows:
            experiments = json.loads(row["shared_experiment_ids"] or "[]")
            if not experiments:
                continue
            results.append(
                {
                    "user_id_a": row["user_id_a"],
                    "user_id_b": row["user_id_b"],
                    "combined_strength": float(row["combined_strength"]),
                    "experiments": experiments,
                }
            )
        return results

    def open_support_tickets(self) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT ticket_id, user_id, severity, category, ticket_timestamp
            FROM support_tickets WHERE status = 'open'
            """
        ).fetchall()
        return [dict(r) for r in rows]

    def feature_exposure_by_community(self, graph_layer: str = "layer2") -> dict[int, float]:
        """Fraction of community members exposed to rollout feature."""
        exposed_users = {
            r["user_id"]
            for r in self.conn.execute(
                "SELECT user_id FROM feature_exposure_log WHERE exposed_flag = 1"
            )
        }
        comm_users: dict[int, list[str]] = defaultdict(list)
        rows = self.conn.execute(
            """
            SELECT node_id, community_id FROM node_metrics
            WHERE graph_layer = ? AND node_type = 'user' AND community_id IS NOT NULL
            GROUP BY node_id, community_id
            """,
            (graph_layer,),
        ).fetchall()
        for row in rows:
            comm_users[int(row["community_id"])].append(row["node_id"])

        rates: dict[int, float] = {}
        for comm_id, members in comm_users.items():
            if not members:
                continue
            exposed = sum(1 for u in members if u in exposed_users)
            rates[comm_id] = exposed / len(members)
        return rates

"""Load cached graphs, metrics, and use case results for the dashboard."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

import networkx as nx
import pandas as pd

from config.env import get, resolve_path
from graphs.cache import load_graph, load_projections
from use_cases.base import UseCaseResult
from use_cases.context import UseCaseContext
from use_cases.registry import run_all

from dashboard.explainability_display import item_involves_user

try:
    from analytics.pyg.predictions import load_predictions
except ImportError:
    def load_predictions(*_args, **_kwargs):
        return pd.DataFrame()


@dataclass
class DashboardData:
    db_path: Path
    graphs: dict[str, nx.Graph] = field(default_factory=dict)
    projections: dict[str, nx.Graph] = field(default_factory=dict)
    ranked_users: pd.DataFrame = field(default_factory=pd.DataFrame)
    users_lookup: dict[str, dict] = field(default_factory=dict)
    clusters: pd.DataFrame = field(default_factory=pd.DataFrame)
    layer3_items: pd.DataFrame = field(default_factory=pd.DataFrame)
    use_case_results: dict[str, UseCaseResult] = field(default_factory=dict)
    predictions: pd.DataFrame = field(default_factory=pd.DataFrame)
    training_metadata: dict = field(default_factory=dict)
    alerts: list[dict] = field(default_factory=list)
    ready: bool = False
    error: str | None = None

    @classmethod
    def load(cls) -> "DashboardData":
        db_path = resolve_path("DATABASE_PATH", "data/synthetic.db")
        data = cls(db_path=db_path)

        if not db_path.is_file():
            data.error = (
                f"Database not found at {db_path}. "
                "Run: python generator/run_generator.py --scale dev && "
                "python graphs/builder.py --all-layers && python analytics/networkx_metrics.py"
            )
            return data

        graphs_dir = resolve_path("GRAPHS_DIR", "data/graphs")
        if not (graphs_dir / "layer1.gpickle").is_file():
            data.error = (
                f"Graph cache missing in {graphs_dir}. Run: python graphs/builder.py --all-layers"
            )
            return data

        try:
            data.graphs = {
                "layer1": load_graph(1),
                "layer2": load_graph(2),
                "layer3": load_graph(3),
                "layer4": load_graph(4),
            }
            data.projections = load_projections()
            data._load_users_and_rankings(db_path)
            data._load_clusters(db_path)
            data._load_layer3_table(db_path)
            with UseCaseContext() as ctx:
                data.use_case_results = run_all(ctx)
            data.predictions = load_predictions()
            try:
                from analytics.pyg.predictions import load_training_metadata

                data.training_metadata = load_training_metadata()
            except ImportError:
                data.training_metadata = {}
            data._build_alerts()
            data.ready = True
        except Exception as exc:
            data.error = str(exc)
        return data

    def _load_users_and_rankings(self, db_path: Path) -> None:
        conn = sqlite3.connect(db_path)
        users = pd.read_sql_query(
            "SELECT user_id, display_name, organization_id FROM users", conn
        )
        metrics = pd.read_sql_query(
            """
            SELECT node_id, graph_layer, metric_name, metric_value, community_id
            FROM node_metrics WHERE node_type = 'user'
            """,
            conn,
        )
        conn.close()

        self.users_lookup = {
            row["user_id"]: {
                "display_name": row["display_name"],
                "organization_id": row["organization_id"],
            }
            for _, row in users.iterrows()
        }

        communities = (
            metrics.dropna(subset=["community_id"])
            .drop_duplicates(subset=["node_id", "graph_layer"])
            .pivot(index="node_id", columns="graph_layer", values="community_id")
        )
        if not communities.empty:
            communities.columns = [f"{layer}_community_id" for layer in communities.columns]
            communities = communities.reset_index().rename(columns={"node_id": "user_id"})

        pivot = metrics.pivot_table(
            index="node_id",
            columns=["graph_layer", "metric_name"],
            values="metric_value",
            aggfunc="first",
        )
        if not pivot.empty:
            pivot.columns = [f"{layer}_{metric}" for layer, metric in pivot.columns]
            pivot = pivot.reset_index().rename(columns={"node_id": "user_id"})
            ranked = users.merge(pivot, on="user_id", how="left")
        else:
            ranked = users.copy()
        if not communities.empty:
            ranked = ranked.merge(communities, on="user_id", how="left")

        ranked["display_name_lower"] = ranked["display_name"].str.lower()
        if "layer1_eigenvector" in ranked.columns:
            ranked["score"] = ranked["layer1_eigenvector"].fillna(0)
        else:
            ranked["score"] = 0
        ranked = ranked.sort_values("score", ascending=False)
        ranked["rank"] = range(1, len(ranked) + 1)
        total = len(ranked)
        ranked["percentile"] = ranked["rank"].apply(lambda r: f"top {int(r / total * 100) or 1}%")
        self.ranked_users = ranked

    def _load_clusters(self, db_path: Path) -> None:
        conn = sqlite3.connect(db_path)
        clusters = pd.read_sql_query(
            "SELECT community_id, graph_layer, node_count, density FROM cluster_metrics",
            conn,
        )
        conn.close()
        self.clusters = clusters[clusters["graph_layer"] == "layer2"].copy()

    def _load_layer3_table(self, db_path: Path) -> None:
        conn = sqlite3.connect(db_path)
        self.layer3_items = pd.read_sql_query(
            """
            SELECT u.display_name, i.title AS item, ui.interaction_type, ui.usage_total
            FROM user_item_interactions ui
            JOIN users u ON u.user_id = ui.user_id
            JOIN items i ON i.item_id = ui.item_id
            ORDER BY ui.usage_total DESC
            LIMIT 500
            """,
            conn,
        )
        conn.close()

    def _build_alerts(self) -> None:
        self.alerts = []
        for uc_id, result in self.use_case_results.items():
            for item in result.flagged[:20]:
                self.alerts.append(
                    {
                        "use_case": result.title,
                        "use_case_id": uc_id,
                        "node_id": item.node_id,
                        "label": item.label,
                        "score": round(item.score, 4),
                        "explanation": item.explanation,
                    }
                )

    def search_users(self, query: str) -> list[str]:
        q = query.strip().lower()
        if not q:
            return []
        matches = self.ranked_users[self.ranked_users["display_name_lower"].str.contains(q, na=False)]
        return matches["user_id"].head(10).tolist()

    def user_display(self, user_id: str) -> str:
        return self.users_lookup.get(user_id, {}).get("display_name", user_id)

    def user_stats(self, user_id: str) -> dict:
        """Return rank/score/metric snapshot for hover cards and graph tooltips."""
        if not user_id:
            return {}
        row = self.ranked_users[self.ranked_users["user_id"] == user_id]
        if row.empty:
            return {
                "user_id": user_id,
                "display_name": self.user_display(user_id),
                "node_type": "user",
            }
        record = row.iloc[0]
        stats = {
            "user_id": user_id,
            "display_name": record.get("display_name", user_id),
            "rank": int(record["rank"]) if pd.notna(record.get("rank")) else None,
            "score": float(record["score"]) if pd.notna(record.get("score")) else None,
            "percentile": record.get("percentile"),
            "node_type": "user",
        }
        for col in ("layer1_degree", "layer1_betweenness", "layer2_degree", "layer1_eigenvector"):
            if col in record.index and pd.notna(record[col]):
                stats[col] = float(record[col])
        return stats

    def user_stats_lookup(self, node_ids: list[str] | None = None) -> dict[str, dict]:
        if node_ids is None:
            return {row["user_id"]: self.user_stats(row["user_id"]) for _, row in self.ranked_users.iterrows()}
        return {node_id: self.user_stats(node_id) for node_id in node_ids}

    def get_graph_for_layer(self, layer: str) -> nx.Graph:
        if layer in ("all", None):
            layer = "layer1"
        return self.graphs.get(layer, self.graphs["layer1"])

    def sample_item_options(self) -> list[dict]:
        if self.layer3_items.empty:
            return [{"label": "Demo item A", "value": "demo_a"}, {"label": "Demo item B", "value": "demo_b"}]
        items = self.layer3_items["item"].drop_duplicates().head(25)
        return [{"label": str(title), "value": str(title)} for title in items]

    def cluster_members(self, community_id: int, limit: int = 15) -> tuple[list[str], int]:
        col = "layer2_community_id"
        if col not in self.ranked_users.columns:
            return [], 0
        members = self.ranked_users[self.ranked_users[col] == community_id]
        total = len(members)
        if total == 0:
            return [], 0
        return members["user_id"].head(limit).tolist(), total

    def flags_for_user(self, user_id: str) -> list[tuple[str, str, object]]:
        """Return (use_case_id, title, FlaggedItem) tuples for a user."""
        hits: list[tuple[str, str, object]] = []
        for uc_id, result in self.use_case_results.items():
            for item in result.flagged:
                if item_involves_user(item, user_id):
                    hits.append((uc_id, result.title, item))
        return hits

    def ab_contamination_connections(self, user_id: str) -> tuple[list[dict], list[str]]:
        """Connected contamination partners and shared experiment names for exclude flow."""
        result = self.use_case_results.get("ab_contamination")
        if not result:
            return [], ["A/B test 1", "A/B test 2"]

        connections: dict[str, dict] = {}
        tests: set[str] = set()
        for item in result.flagged:
            pair_id = item.node_id or ""
            if "|" not in pair_id:
                continue
            user_a, user_b = pair_id.split("|", 1)
            if user_id not in (user_a, user_b):
                continue
            partner = user_b if user_a == user_id else user_a
            strength = float(item.metrics.get("combined_strength", 0.0))
            for experiment in (item.extra or {}).get("experiments", []):
                tests.add(str(experiment))
            existing = connections.get(partner)
            if existing is None or strength > existing["strength"]:
                connections[partner] = {
                    "user_id": partner,
                    "display_name": self.user_display(partner),
                    "strength": strength,
                }

        ordered = sorted(connections.values(), key=lambda row: row["strength"], reverse=True)
        test_list = sorted(tests) if tests else ["A/B test 1", "A/B test 2"]
        return ordered, test_list

    def layer3_for_user(self, user_id: str | None) -> list[dict]:
        if not user_id or self.layer3_items.empty:
            return self.layer3_items.head(100).to_dict("records")
        name = self.user_display(user_id)
        filtered = self.layer3_items[self.layer3_items["display_name"] == name]
        if filtered.empty:
            return []
        return filtered.head(100).to_dict("records")

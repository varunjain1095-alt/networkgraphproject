"""Cluster hover card for bubble chart."""

from __future__ import annotations

from dash import html

from dashboard.data_loader import DashboardData
from dashboard.graph_hover import HOVER_CARD_HIDDEN, HOVER_CARD_VISIBLE

CLUSTER_MEMBER_CAP = 15


def build_cluster_hover_card(data: DashboardData, community_id: int | None) -> tuple[list, dict]:
    if community_id is None:
        return [], HOVER_CARD_HIDDEN

    user_ids, total = data.cluster_members(community_id, limit=CLUSTER_MEMBER_CAP)
    if total == 0:
        return [
            html.Div(f"Community {community_id}", style={"fontWeight": 600, "marginBottom": "0.35rem"}),
            html.P("No member IDs found in the current sample.", style={"fontSize": "0.85rem", "margin": 0}),
        ], HOVER_CARD_VISIBLE

    lines = [html.Li(uid, style={"fontSize": "0.8rem", "fontFamily": "monospace"}) for uid in user_ids]
    footer = f"Showing {len(user_ids)} of {total} user IDs"
    if total > len(user_ids):
        footer += " (larger clusters are capped like the ego network view)"

    return [
        html.Div(f"Community {community_id}", style={"fontWeight": 600, "fontSize": "0.95rem", "marginBottom": "0.35rem"}),
        html.P(f"{total} users in this cluster", style={"fontSize": "0.8rem", "color": "#64748b", "margin": "0 0 0.35rem"}),
        html.Ul(lines, style={"margin": 0, "paddingLeft": "1.1rem", "maxHeight": "220px", "overflowY": "auto"}),
        html.P(footer, style={"fontSize": "0.7rem", "color": "#94a3b8", "margin": "0.35rem 0 0"}),
    ], {
        **HOVER_CARD_VISIBLE,
        "left": "12px",
        "right": "auto",
        "top": "12px",
    }

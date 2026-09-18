"""Hover card content for ego-network nodes."""

from __future__ import annotations

from dash import html

from dashboard.data_loader import DashboardData
from dashboard.demo_profiles import get_demo_profile


def build_hover_card(data: DashboardData, node_data: dict | None, layer: str = "layer1") -> list:
    """Render a compact info card for a hovered graph node."""
    if not node_data:
        return []

    user_id = str(node_data.get("id", ""))
    profile = get_demo_profile(user_id)
    is_center = node_data.get("is_center") in (True, "true", "True", 1)

    if profile:
        title = profile.name
        rows = profile.as_rows()
    else:
        fallback_name = data.user_display(user_id) if user_id else "Unknown user"
        title = fallback_name if fallback_name != user_id else user_id
        rows = [("User ID", user_id or "—")]

    if is_center:
        rows = [*rows, ("Role", "Ego center")]

    stats = data.user_stats(user_id) if user_id else {}
    if layer in ("layer1", "all"):
        if stats.get("layer1_degree") is not None:
            rows.append(("Relationship ties", str(int(stats["layer1_degree"]))))
        if stats.get("layer1_betweenness") is not None:
            rows.append(("Bridging score", f"{stats['layer1_betweenness']:.3f}"))
    elif layer == "layer2":
        if stats.get("layer2_degree") is not None:
            rows.append(("Co-activity partners", str(int(stats["layer2_degree"]))))
    elif layer == "layer4":
        node_type = node_data.get("node_type", "user")
        if node_type != "user":
            rows.append(("Node type", node_type.replace("_", " ").title()))
        if stats.get("rank") is not None:
            rows.append(("Influence rank", str(stats["rank"])))

    dl_children: list = []
    for label, value in rows:
        dl_children.extend(
            [
                html.Dt(label, style={"fontSize": "0.75rem", "color": "#64748b", "margin": 0}),
                html.Dd(value, style={"fontSize": "0.85rem", "margin": "0 0 0.35rem 0"}),
            ]
        )

    footer = "Click to select"
    if not profile:
        footer = "Demo profile not set · click to select"

    return [
        html.Div(
            title,
            style={"fontWeight": 600, "fontSize": "0.95rem", "marginBottom": "0.35rem"},
        ),
        html.Dl(dl_children, style={"margin": 0}),
        html.P(
            footer,
            style={"fontSize": "0.7rem", "color": "#94a3b8", "margin": "0.35rem 0 0"},
        ),
    ]


HOVER_CARD_VISIBLE = {
    "display": "block",
    "position": "absolute",
    "top": "12px",
    "right": "12px",
    "zIndex": 10,
    "minWidth": "200px",
    "maxWidth": "260px",
    "padding": "0.75rem 0.85rem",
    "background": "rgba(255, 255, 255, 0.97)",
    "border": "1px solid #e2e8f0",
    "borderRadius": "8px",
    "boxShadow": "0 8px 24px rgba(15, 23, 42, 0.12)",
    "pointerEvents": "none",
}

HOVER_CARD_HIDDEN = {"display": "none"}

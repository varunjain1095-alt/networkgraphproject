"""Cluster community bubble visualization for the Clusters tab."""

from __future__ import annotations

import math

from dash import html

from dashboard.data_loader import DashboardData
from dashboard.explainability_display import sanitize_display_text

CLUSTER_TAB_INTRO = sanitize_display_text(
    "Communities are groups of users who interact more with each other than with the rest of "
    "the network. Each bubble is one community from the shared activity layer. Bubble size "
    "reflects how many users belong to the cluster; darker color means higher internal density "
    "(members are more connected to each other). Select a bubble or table row to focus on one "
    "community."
)


def cluster_explainability(data: DashboardData, cluster_id: int | None) -> list:
    if cluster_id is None or data.clusters.empty:
        return [
            html.P(CLUSTER_TAB_INTRO, style={"color": "#64748b"}),
            html.P("Select a community from the table or bubble chart to see details."),
        ]

    match = data.clusters[data.clusters["community_id"] == cluster_id]
    if match.empty:
        return [html.P(f"Community {cluster_id} was not found in the current sample.")]

    row = match.iloc[0]
    count = int(row["node_count"])
    density = float(row["density"])
    density_label = "high" if density >= 0.4 else "moderate" if density >= 0.2 else "lower"

    return [
        html.H4(f"Community {cluster_id}"),
        html.P(
            sanitize_display_text(
                f"This community has {count} users and {density_label} internal density "
                f"({density:.2f}). Members share more activity with each other than with "
                "users outside the group."
            )
        ),
        html.P(
            sanitize_display_text(
                "Use this view to compare community size and cohesion at a glance, then drill "
                "into product use cases that target whole clusters rather than individuals."
            ),
            style={"color": "#64748b", "fontSize": "0.9rem"},
        ),
    ]


def _density_color(density: float, max_density: float) -> str:
    if max_density <= 0:
        return "rgba(14, 165, 233, 0.35)"
    t = min(1.0, density / max_density)
    # Light sky to deep blue
    r = int(186 - t * 120)
    g = int(230 - t * 100)
    b = int(253 - t * 40)
    return f"rgb({r}, {g}, {b})"


def build_cluster_bubble_panel(data: DashboardData, selected_cluster_id: int | None = None) -> list:
    if data.clusters.empty:
        return [
            html.P(CLUSTER_TAB_INTRO, style={"color": "#64748b", "marginTop": 0}),
            html.P("No community metrics are available for the current dataset."),
        ]

    clusters = data.clusters.sort_values("node_count", ascending=False)
    max_count = max(float(clusters["node_count"].max()), 1.0)
    max_density = max(float(clusters["density"].max()), 0.001)

    bubbles: list = []
    for _, row in clusters.iterrows():
        comm_id = int(row["community_id"])
        count = int(row["node_count"])
        density = float(row["density"])
        size = 48 + math.sqrt(count / max_count) * 132
        selected = selected_cluster_id == comm_id
        bubbles.append(
            html.Div(
                [
                    html.Div(str(comm_id), style={"fontWeight": 700, "fontSize": "0.95rem"}),
                    html.Div(f"{count} users", style={"fontSize": "0.75rem", "opacity": 0.85}),
                    html.Div(f"density {density:.2f}", style={"fontSize": "0.7rem", "opacity": 0.75}),
                ],
                className="cluster-bubble",
                **{"data-comm-id": str(comm_id)},
                title=f"Community {comm_id}: {count} users, density {density:.2f}",
                style={
                    "width": f"{size}px",
                    "height": f"{size}px",
                    "borderRadius": "50%",
                    "background": _density_color(density, max_density),
                    "border": "3px solid #1d4ed8" if selected else "2px solid rgba(255,255,255,0.9)",
                    "boxShadow": "0 4px 14px rgba(15, 23, 42, 0.12)" if not selected else "0 0 0 3px rgba(29, 78, 216, 0.25)",
                    "display": "flex",
                    "flexDirection": "column",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "textAlign": "center",
                    "color": "#0f172a",
                    "margin": "8px",
                    "cursor": "default",
                    "flexShrink": 0,
                },
            )
        )

    legend = html.Div(
        [
            html.Span("Size = user count", style={"marginRight": "1rem"}),
            html.Span("Color intensity = density", style={"marginRight": "1rem"}),
            html.Span("Blue outline = selected", style={}),
        ],
        style={"fontSize": "0.8rem", "color": "#64748b", "marginTop": "0.75rem"},
    )

    return [
        html.P(CLUSTER_TAB_INTRO, style={"color": "#475569", "marginTop": 0, "lineHeight": "1.45"}),
        html.Div(
            bubbles,
            style={
                "display": "flex",
                "flexWrap": "wrap",
                "alignItems": "center",
                "justifyContent": "center",
                "alignContent": "center",
                "minHeight": "420px",
                "padding": "1rem",
            },
        ),
        legend,
    ]

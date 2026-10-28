"""Dashboard page layout."""

from __future__ import annotations

from dash import dcc, html
import dash_ag_grid as dag
import dash_cytoscape as cyto

from dashboard.data_loader import DashboardData
from dashboard.ids import IDs
from dashboard.pm_actions import build_pm_panel_area, build_pm_stores

CYTOSCAPE_LAYOUT = {
    "name": "cose",
    "animate": True,
    "padding": 48,
    "nodeRepulsion": 12000,
    "idealEdgeLength": 110,
    "nodeOverlap": 48,
    "componentSpacing": 160,
    "edgeElasticity": 120,
    "gravity": 0.2,
    "numIter": 1000,
}

CYTOSCAPE_STYLESHEET = [
    {
        "selector": "node",
        "style": {
            "width": 26,
            "height": 26,
            "font-size": "10px",
            "color": "#334155",
            "text-valign": "bottom",
            "text-halign": "center",
            "text-margin-y": 8,
            "text-outline-color": "#ffffff",
            "text-outline-width": 2,
        },
    },
    {
        "selector": "node:selected",
        "style": {
            "label": "data(label)",
            "border-width": 3,
            "border-color": "#1d4ed8",
        },
    },
    {"selector": "edge", "style": {"width": 1.5, "line-color": "#cbd5e1", "opacity": 0.85}},
    {"selector": ".user", "style": {"background-color": "#0ea5e9"}},
    {"selector": ".item", "style": {"background-color": "#94a3b8"}},
    {"selector": ".source", "style": {"background-color": "#f59e0b"}},
    {"selector": ".contribution", "style": {"background-color": "#a855f7"}},
    {
        "selector": "node.center",
        "style": {
            "background-color": "#22c55e",
            "width": 38,
            "height": 38,
            "border-width": 3,
            "border-color": "#15803d",
        },
    },
    {
        "selector": "node.center:selected",
        "style": {
            "label": "data(label)",
            "background-color": "#22c55e",
            "border-width": 3,
            "border-color": "#14532d",
        },
    },
]

RANKED_COLS = [
    {"field": "rank", "headerName": "Rank", "width": 80},
    {"field": "display_name", "headerName": "User", "flex": 1},
    {"field": "score", "headerName": "Score", "width": 100},
    {"field": "percentile", "headerName": "Percentile", "width": 110},
    {"field": "user_id", "headerName": "ID", "hide": True},
]

ALERT_COLS = [
    {"field": "use_case", "headerName": "Use case", "flex": 1},
    {"field": "label", "headerName": "Flagged", "flex": 1},
    {"field": "score", "headerName": "Score", "width": 90},
    {"field": "node_id", "headerName": "ID", "hide": True},
]

USE_CASE_COLS = [
    {"field": "rank", "headerName": "Rank", "width": 70},
    {"field": "label", "headerName": "Label", "flex": 1},
    {"field": "score", "headerName": "Score", "width": 90},
    {"field": "node_id", "headerName": "ID", "hide": True},
]

CLUSTER_COLS = [
    {"field": "community_id", "headerName": "Cluster", "width": 90},
    {"field": "node_count", "headerName": "Users", "width": 90},
    {"field": "density", "headerName": "Density", "width": 100},
]

LAYER3_COLS = [
    {"field": "display_name", "headerName": "User", "flex": 1},
    {"field": "item", "headerName": "Item", "flex": 1},
    {"field": "interaction_type", "headerName": "Type", "width": 100},
    {"field": "usage_total", "headerName": "Usage", "width": 90},
]


def _grid(grid_id: str, column_defs: list, row_data: list, height: str = "320px") -> dag.AgGrid:
    return dag.AgGrid(
        id=grid_id,
        columnDefs=column_defs,
        rowData=row_data,
        defaultColDef={"sortable": True, "filter": True, "resizable": True},
        dashGridOptions={"rowSelection": "single", "animateRows": True},
        style={"height": height, "width": "100%"},
        className="ag-theme-alpine",
    )


def build_layout(data: DashboardData) -> html.Div:
    if not data.ready:
        return html.Div(
            [
                html.H2("Network Graph Intelligence"),
                html.Div(
                    data.error or "Dashboard data not available.",
                    id=IDs.STARTUP_BANNER,
                    style={"color": "#b91c1c", "padding": "1rem", "border": "1px solid #fecaca"},
                ),
            ],
            style={"padding": "2rem", "fontFamily": "Segoe UI, sans-serif"},
        )

    ranked_rows = data.ranked_users.head(100)[["rank", "display_name", "score", "percentile", "user_id"]].to_dict("records")
    default_user_id = ranked_rows[0]["user_id"] if ranked_rows else None
    use_case_options = [{"label": r.title, "value": uc_id} for uc_id, r in data.use_case_results.items()]
    default_uc = use_case_options[0]["value"] if use_case_options else None
    cluster_rows = data.clusters.head(50).to_dict("records") if not data.clusters.empty else []
    layer3_rows = data.layer3_items.head(100).to_dict("records") if not data.layer3_items.empty else []
    item_options = data.sample_item_options()

    return html.Div(
        [
            dcc.Store(id=IDs.SELECTED_NODE, data={"user_id": default_user_id, "source": "ranked" if default_user_id else None}),
            dcc.Store(id=IDs.CLUSTER_HOVER_STORE, data=None),
            *build_pm_stores(),
            html.Header(
                [
                    html.H1("Network Graph Intelligence", style={"margin": 0}),
                    html.P("Explore network structure and product use cases", style={"margin": 0, "opacity": 0.7}),
                ],
                style={"padding": "1rem 1.5rem", "borderBottom": "1px solid #e2e8f0"},
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("Graph layer"),
                            dcc.Dropdown(
                                id=IDs.ACTIVE_LAYER,
                                options=[
                                    {"label": "Relationships", "value": "layer1"},
                                    {"label": "Shared activity", "value": "layer2"},
                                    {"label": "Ownership patterns (table)", "value": "layer3"},
                                    {"label": "Reviews and curators", "value": "layer4"},
                                ],
                                value="layer1",
                                clearable=False,
                            ),
                        ],
                        style={"width": "260px"},
                    ),
                    html.Div(
                        [
                            html.Label("Search user"),
                            dcc.Input(id=IDs.SEARCH_INPUT, type="text", placeholder="Search by name...", debounce=True, style={"width": "100%"}),
                        ],
                        style={"width": "240px"},
                    ),
                    html.Div(
                        [
                            html.Label("Importance"),
                            dcc.RadioItems(
                                id=IDs.IMPORTANCE_TOGGLE,
                                options=[
                                    {"label": "Most important", "value": "most"},
                                    {"label": "Least important", "value": "least"},
                                ],
                                value="most",
                                inline=True,
                            ),
                        ],
                        style={"width": "280px"},
                    ),
                ],
                style={"display": "flex", "gap": "1.5rem", "padding": "1rem 1.5rem", "flexWrap": "wrap"},
            ),
            dcc.Tabs(
                id=IDs.ACTIVE_TAB,
                value="ranked",
                children=[
                    dcc.Tab(label="Ranked list", value="ranked"),
                    dcc.Tab(label="Alerts", value="alerts"),
                    dcc.Tab(label="Clusters", value="clusters"),
                    dcc.Tab(label="Use cases", value="usecases"),
                ],
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(id="left-panel-ranked", children=[
                                html.H4("Top users by influence"),
                                _grid(IDs.RANKED_TABLE, RANKED_COLS, ranked_rows),
                                html.Div(id=IDs.RANKED_PM_ACTIONS),
                            ]),
                            html.Div(
                                id="left-panel-alerts",
                                style={"display": "none"},
                                children=[
                                    html.H4("Flagged entries"),
                                    _grid(IDs.ALERTS_TABLE, ALERT_COLS, data.alerts),
                                    html.Div(id=IDs.EXCLUDE_LIST_PANEL),
                                ],
                            ),
                            html.Div(id="left-panel-clusters", style={"display": "none"}, children=[html.H4("Communities"), _grid(IDs.CLUSTER_TABLE, CLUSTER_COLS, cluster_rows)]),
                            html.Div(
                                id="left-panel-usecases",
                                style={"display": "none"},
                                children=[
                                    html.Div(id=IDs.USE_CASE_HEADER, children=[html.H4("Use case results")]),
                                    dcc.Dropdown(id=IDs.ACTIVE_USE_CASE, options=use_case_options, value=default_uc, clearable=False),
                                    html.Div(style={"height": "8px"}),
                                    _grid(IDs.USE_CASE_TABLE, USE_CASE_COLS, [], height="280px"),
                                ],
                            ),
                        ],
                        style={"width": "42%", "padding": "1rem"},
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        id=IDs.ALERTS_CONTEXT_WRAP,
                                        children=[html.Div(id=IDs.ALERTS_CONTEXT_CARD)],
                                        style={"display": "none"},
                                    ),
                                    html.Div(
                                        [
                                            html.P(
                                                id=IDs.GRAPH_INTRO,
                                                style={
                                                    "fontSize": "0.9rem",
                                                    "color": "#475569",
                                                    "marginBottom": "0.65rem",
                                                    "lineHeight": "1.45",
                                                },
                                            ),
                                            html.Div(
                                                id=IDs.GRAPH_MAIN,
                                                children=[
                                                    html.Div(
                                                        id=IDs.GRAPH_CYTO_WRAP,
                                                        children=[
                                                            cyto.Cytoscape(
                                                                id=IDs.GRAPH,
                                                                elements=[],
                                                                layout=CYTOSCAPE_LAYOUT,
                                                                stylesheet=CYTOSCAPE_STYLESHEET,
                                                                style={"width": "100%", "height": "100%"},
                                                                boxSelectionEnabled=False,
                                                                autounselectify=False,
                                                                userPanningEnabled=True,
                                                                userZoomingEnabled=True,
                                                                clearOnUnhover=True,
                                                            ),
                                                            html.Div(id=IDs.GRAPH_HOVER_CARD, style={"display": "none"}),
                                                        ],
                                                        style={
                                                            "position": "relative",
                                                            "width": "100%",
                                                            "height": "100%",
                                                        },
                                                    ),
                                                    html.Div(
                                                        id=IDs.CLUSTER_PANEL,
                                                        children=[
                                                            html.Div(id="cluster-bubble-area"),
                                                            html.Div(id=IDs.CLUSTER_HOVER_CARD, style={"display": "none"}),
                                                        ],
                                                        style={
                                                            "display": "none",
                                                            "height": "100%",
                                                            "overflowY": "auto",
                                                            "padding": "1rem",
                                                            "background": "#ffffff",
                                                            "position": "relative",
                                                        },
                                                    ),
                                                    html.Div(
                                                        id=IDs.LAYER3_PANEL,
                                                        children=[
                                                            html.Div(id="layer3-intro"),
                                                            html.H5("Item interactions", style={"marginBottom": "0.35rem"}),
                                                            _grid(IDs.LAYER3_TABLE, LAYER3_COLS, layer3_rows, height="220px"),
                                                            html.Div(id="layer3-heatmap"),
                                                        ],
                                                        style={"display": "none", "height": "100%", "overflowY": "auto", "padding": "1rem"},
                                                    ),
                                                ],
                                                style={
                                                    "width": "100%",
                                                    "height": "600px",
                                                    "border": "1px solid #e2e8f0",
                                                    "borderRadius": "8px",
                                                    "overflow": "hidden",
                                                    "background": "#fafafa",
                                                },
                                            ),
                                            html.P(
                                                id=IDs.GRAPH_CAPTION,
                                                style={"fontSize": "0.9rem", "color": "#64748b", "marginTop": "0.5rem"},
                                            ),
                                            build_pm_panel_area(item_options),
                                        ],
                                        style={"flex": "1", "minWidth": 0},
                                    ),
                                ],
                                style={"display": "flex", "gap": "0.75rem", "width": "100%", "alignItems": "flex-start"},
                            ),
                        ],
                        style={"width": "58%", "padding": "1rem"},
                    ),
                ],
                style={"display": "flex"},
            ),
            html.Div(
                [
                    html.Div(id=IDs.PM_FEEDBACK, style={"fontSize": "0.85rem", "padding": "0 1.5rem", "minHeight": "1.25rem"}),
                    html.H3("Explainability"),
                    html.Div(id=IDs.EXPLAIN_PANEL, style={"padding": "0.5rem 0"}),
                ],
                style={"padding": "1rem 0", "borderTop": "1px solid #e2e8f0", "background": "#f8fafc"},
            ),
        ],
        style={"fontFamily": "Segoe UI, sans-serif", "maxWidth": "1400px", "margin": "0 auto"},
    )

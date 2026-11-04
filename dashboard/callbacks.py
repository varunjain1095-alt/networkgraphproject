"""Dash callbacks — linked views."""

from __future__ import annotations

from dash import Input, Output, State, ctx, html
from dash.exceptions import PreventUpdate

from dashboard.alert_context import (
    ALERTS_COLUMN_HIDDEN,
    ALERTS_COLUMN_VISIBLE,
    build_alerts_context_card,
)
from dashboard.cluster_view import CLUSTER_TAB_INTRO, build_cluster_bubble_panel, cluster_explainability
from dashboard.data_loader import DashboardData
from dashboard.explainability import build_explanation
from dashboard.graph_hover import HOVER_CARD_HIDDEN, HOVER_CARD_VISIBLE, build_hover_card
from dashboard.graph_views import ego_view, layout_for_layer
from dashboard.ids import IDs
from dashboard.layer_copy import layer_graph_intro
from dashboard.layer_panels import build_coownership_grid, build_ownership_intro
from dashboard.cluster_hover import build_cluster_hover_card
from dashboard.layout import CYTOSCAPE_LAYOUT
from dashboard.pm_callbacks import register_pm_callbacks

ALERTS_GRAPH_PROMPT = "Select a flagged user to see why they were flagged."


def register_callbacks(app, data: DashboardData) -> None:
    register_pm_callbacks(app, data)

    @app.callback(
        Output("left-panel-ranked", "style"),
        Output("left-panel-alerts", "style"),
        Output("left-panel-clusters", "style"),
        Output("left-panel-usecases", "style"),
        Input(IDs.ACTIVE_TAB, "value"),
    )
    def switch_tab(tab):
        hidden = {"display": "none"}
        shown = {"display": "block"}
        return (
            shown if tab == "ranked" else hidden,
            shown if tab == "alerts" else hidden,
            shown if tab == "clusters" else hidden,
            shown if tab == "usecases" else hidden,
        )

    @app.callback(
        Output(IDs.USE_CASE_TABLE, "rowData"),
        Output(IDs.USE_CASE_HEADER, "children"),
        Input(IDs.ACTIVE_USE_CASE, "value"),
    )
    def update_use_case_table(uc_id):
        if not uc_id or uc_id not in data.use_case_results:
            raise PreventUpdate
        result = data.use_case_results[uc_id]
        items = result.sorted()
        rows = [
            {
                "rank": item.rank,
                "label": item.label,
                "score": round(item.score, 4),
                "node_id": item.node_id,
            }
            for item in items[:50]
        ]
        return rows, html.H4(f"{result.title} ({len(result.flagged)} flagged)")

    @app.callback(
        Output(IDs.ALERTS_CONTEXT_CARD, "children"),
        Output(IDs.ALERTS_CONTEXT_WRAP, "style"),
        Input(IDs.SELECTED_NODE, "data"),
        Input(IDs.ACTIVE_TAB, "value"),
    )
    def update_alerts_context_card(selected, tab):
        if tab != "alerts":
            return [], ALERTS_COLUMN_HIDDEN
        user_id = (selected or {}).get("user_id")
        if not user_id:
            return [], ALERTS_COLUMN_HIDDEN
        return build_alerts_context_card(data, user_id), ALERTS_COLUMN_VISIBLE

    @app.callback(
        Output(IDs.SELECTED_NODE, "data"),
        Input(IDs.RANKED_TABLE, "selectedRows"),
        Input(IDs.ALERTS_TABLE, "selectedRows"),
        Input(IDs.USE_CASE_TABLE, "selectedRows"),
        Input(IDs.CLUSTER_TABLE, "selectedRows"),
        Input(IDs.SEARCH_INPUT, "value"),
        State(IDs.SELECTED_NODE, "data"),
    )
    def select_node(ranked_rows, alert_rows, uc_rows, cluster_rows, search, current):
        trigger = ctx.triggered_id
        if trigger == IDs.RANKED_TABLE and ranked_rows:
            return {"user_id": ranked_rows[0].get("user_id"), "source": "ranked"}
        if trigger == IDs.ALERTS_TABLE and alert_rows:
            row = alert_rows[0]
            uid = row.get("node_id", "")
            if "|" in uid:
                uid = uid.split("|")[0]
            if uid.startswith("community_"):
                return {
                    "user_id": None,
                    "source": "alerts",
                    "use_case_id": row.get("use_case_id"),
                }
            return {
                "user_id": uid,
                "source": "alerts",
                "use_case_id": row.get("use_case_id"),
            }
        if trigger == IDs.USE_CASE_TABLE and uc_rows:
            uid = uc_rows[0].get("node_id", "")
            if "|" in uid:
                uid = uid.split("|")[0]
            if uid.startswith("community_"):
                return current or {"user_id": None, "source": "usecase"}
            return {"user_id": uid, "source": "usecase"}
        if trigger == IDs.CLUSTER_TABLE and cluster_rows:
            return {
                "cluster_id": int(cluster_rows[0]["community_id"]),
                "source": "cluster",
                "user_id": None,
            }
        if trigger == IDs.SEARCH_INPUT and search:
            matches = data.search_users(search)
            if matches:
                return {"user_id": matches[0], "source": "search"}
        raise PreventUpdate

    @app.callback(
        Output(IDs.SELECTED_NODE, "data", allow_duplicate=True),
        Input(IDs.GRAPH, "tapNodeData"),
        prevent_initial_call=True,
    )
    def graph_node_tapped(node):
        if not node:
            raise PreventUpdate
        node_id = node.get("id")
        if not node_id:
            raise PreventUpdate
        return {"user_id": node_id, "source": "graph"}

    @app.callback(
        Output(IDs.GRAPH_HOVER_CARD, "children"),
        Output(IDs.GRAPH_HOVER_CARD, "style"),
        Input(IDs.GRAPH, "mouseoverNodeData"),
        Input(IDs.ACTIVE_LAYER, "value"),
    )
    def show_graph_hover_card(hover, layer):
        if not hover:
            return [], HOVER_CARD_HIDDEN
        active_layer = "layer1" if layer == "all" else (layer or "layer1")
        return build_hover_card(data, hover, layer=active_layer), HOVER_CARD_VISIBLE

    @app.callback(
        Output(IDs.GRAPH_INTRO, "children"),
        Output(IDs.GRAPH, "elements"),
        Output(IDs.GRAPH, "layout"),
        Output(IDs.GRAPH_CAPTION, "children"),
        Output(IDs.GRAPH_CYTO_WRAP, "style"),
        Output(IDs.LAYER3_PANEL, "style"),
        Output("layer3-intro", "children"),
        Output("layer3-heatmap", "children"),
        Output("cluster-bubble-area", "children"),
        Output(IDs.CLUSTER_PANEL, "style"),
        Input(IDs.SELECTED_NODE, "data"),
        Input(IDs.ACTIVE_LAYER, "value"),
        Input(IDs.ACTIVE_TAB, "value"),
    )
    def update_graph_area(selected, layer, tab):
        user_id = (selected or {}).get("user_id")
        cluster_id = (selected or {}).get("cluster_id") if (selected or {}).get("source") == "cluster" else None
        use_case_id = (selected or {}).get("use_case_id")
        active_layer = "layer1" if layer == "all" else (layer or "layer1")

        cyto_style = {"display": "block", "position": "relative", "width": "100%", "height": "100%"}
        cyto_hidden = {"display": "none"}
        layer3_style = {
            "display": "none",
            "height": "100%",
            "overflowY": "auto",
            "padding": "1rem",
            "background": "#ffffff",
        }
        cluster_style = {
            "display": "none",
            "height": "100%",
            "overflowY": "auto",
            "padding": "1rem",
            "background": "#ffffff",
        }

        if tab == "clusters":
            count = len(data.clusters) if not data.clusters.empty else 0
            caption = f"{count} communities from shared activity · darker color = higher density"
            return (
                CLUSTER_TAB_INTRO,
                [],
                CYTOSCAPE_LAYOUT,
                caption,
                cyto_hidden,
                layer3_style,
                [],
                [],
                build_cluster_bubble_panel(data, cluster_id),
                {**cluster_style, "display": "block"},
            )

        if tab == "alerts":
            intro = ALERTS_GRAPH_PROMPT if not user_id else layer_graph_intro(active_layer)
        else:
            intro = layer_graph_intro(active_layer)

        if active_layer == "layer3":
            caption = (
                "Ownership patterns are score and table based. "
                "Use the item table and co-ownership grid to compare taste similarity."
            )
            return (
                intro,
                [],
                CYTOSCAPE_LAYOUT,
                caption,
                cyto_hidden,
                {**layer3_style, "display": "block"},
                build_ownership_intro(data, user_id),
                build_coownership_grid(data, user_id),
                [],
                cluster_style,
            )

        if not user_id:
            caption = (
                ALERTS_GRAPH_PROMPT
                if tab == "alerts"
                else "Select a user to view their ego network."
            )
            return (
                intro,
                [],
                layout_for_layer(active_layer, CYTOSCAPE_LAYOUT),
                caption,
                cyto_style,
                layer3_style,
                [],
                [],
                [],
                cluster_style,
            )

        base = data.get_graph_for_layer(active_layer)
        elements, caption, _meta = ego_view(
            base,
            user_id,
            active_layer,
            stats_provider=data.user_stats_lookup,
        )
        graph_layout = layout_for_layer(active_layer, CYTOSCAPE_LAYOUT)
        if not elements:
            return intro, [], graph_layout, caption, cyto_style, layer3_style, [], [], [], cluster_style

        return intro, elements, graph_layout, caption, cyto_style, layer3_style, [], [], [], cluster_style

    @app.callback(
        Output(IDs.LAYER3_TABLE, "rowData"),
        Input(IDs.SELECTED_NODE, "data"),
        Input(IDs.ACTIVE_LAYER, "value"),
    )
    def update_layer3_table(selected, layer):
        user_id = (selected or {}).get("user_id")
        active_layer = "layer1" if layer == "all" else layer
        if active_layer != "layer3" and not user_id:
            return data.layer3_items.head(100).to_dict("records")
        return data.layer3_for_user(user_id)

    @app.callback(
        Output(IDs.EXPLAIN_PANEL, "children"),
        Input(IDs.SELECTED_NODE, "data"),
        Input(IDs.ACTIVE_LAYER, "value"),
        Input(IDs.ACTIVE_USE_CASE, "value"),
        Input(IDs.ACTIVE_TAB, "value"),
    )
    def update_explanation(selected, layer, uc_id, tab):
        if tab == "clusters":
            cluster_id = (selected or {}).get("cluster_id") if (selected or {}).get("source") == "cluster" else None
            return cluster_explainability(data, cluster_id)

        user_id = (selected or {}).get("user_id")
        active_layer = "layer1" if layer == "all" else (layer or "layer1")
        uc_result = data.use_case_results.get(uc_id) if uc_id else None
        return build_explanation(data, user_id, active_layer, uc_result)

    @app.callback(
        Output(IDs.CLUSTER_HOVER_CARD, "children"),
        Output(IDs.CLUSTER_HOVER_CARD, "style"),
        Input(IDs.CLUSTER_HOVER_STORE, "data"),
        Input(IDs.ACTIVE_TAB, "value"),
    )
    def show_cluster_hover_card(community_id, tab):
        if tab != "clusters":
            return [], {"display": "none"}
        children, style = build_cluster_hover_card(data, community_id)
        return children, style

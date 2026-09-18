"""PM action mock workflow callbacks."""

from __future__ import annotations

from dash import ALL, Input, Output, State, ctx, html, no_update
from dash.exceptions import PreventUpdate

from dashboard.data_loader import DashboardData
from dashboard.ids import IDs
from dashboard.pm_actions import (
    _PANEL_CARD,
    _PANEL_HIDDEN,
    build_exclude_list_panel,
    build_exclude_panel_content,
    pm_actions_section,
    success_message,
)

_PANEL_OPEN = dict(_PANEL_CARD)


def register_pm_callbacks(app, data: DashboardData) -> None:
    @app.callback(
        Output(IDs.RANKED_PM_ACTIONS, "children"),
        Input(IDs.SELECTED_NODE, "data"),
        Input(IDs.ACTIVE_TAB, "value"),
    )
    def update_ranked_pm_actions(selected, tab):
        if tab != "ranked":
            return []
        user_id = (selected or {}).get("user_id")
        if not user_id:
            return html.P(
                "Select a user to see PM actions.",
                style={"fontSize": "0.85rem", "color": "#64748b", "marginTop": "0.5rem"},
            )
        name = data.user_display(user_id)
        return pm_actions_section("ranked", name)

    @app.callback(
        Output(IDs.PM_TARGET_USER, "data"),
        Output(IDs.PM_RECOMMEND_PANEL, "style"),
        Output(IDs.PM_RECOMMEND_USER_LABEL, "children"),
        Output(IDs.PM_FORWARD_PANEL, "style"),
        Output(IDs.PM_FORWARD_USER_LABEL, "children"),
        Output(IDs.PM_EXCLUDE_PANEL, "style"),
        Output(IDs.PM_EXCLUDE_PANEL, "children"),
        Output(IDs.PM_ACTIVE_PANEL, "data"),
        Input({"type": "pm-recommend-btn", "source": ALL}, "n_clicks"),
        Input({"type": "pm-forward-btn", "source": ALL}, "n_clicks"),
        Input({"type": "pm-exclude-btn", "source": ALL, "user": ALL}, "n_clicks"),
        Input(IDs.PM_CLOSE_RECOMMEND, "n_clicks"),
        Input(IDs.PM_CLOSE_FORWARD, "n_clicks"),
        Input(IDs.PM_CLOSE_EXCLUDE, "n_clicks"),
        State(IDs.SELECTED_NODE, "data"),
        prevent_initial_call=True,
    )
    def toggle_pm_panels(
        _rec_clicks,
        _fwd_clicks,
        _exclude_clicks,
        _close_rec,
        _close_fwd,
        _close_excl,
        selected,
    ):
        trigger = ctx.triggered_id
        hidden = {**_PANEL_HIDDEN, **_PANEL_CARD}

        if trigger == IDs.PM_CLOSE_RECOMMEND:
            return no_update, hidden, no_update, no_update, no_update, no_update, no_update, None
        if trigger == IDs.PM_CLOSE_FORWARD:
            return no_update, no_update, no_update, hidden, no_update, no_update, no_update, None
        if trigger == IDs.PM_CLOSE_EXCLUDE:
            return no_update, no_update, no_update, no_update, no_update, hidden, no_update, None

        user_id = (selected or {}).get("user_id")
        if not user_id and not (
            isinstance(trigger, dict) and trigger.get("type") == "pm-exclude-btn"
        ):
            raise PreventUpdate

        if isinstance(trigger, dict) and trigger.get("type") == "pm-exclude-btn":
            main_user_id = trigger.get("user") or user_id
            if not main_user_id:
                raise PreventUpdate
            main_name = data.user_display(main_user_id)
            connections, tests = data.ab_contamination_connections(main_user_id)
            exclude_content = build_exclude_panel_content(main_user_id, main_name, connections, tests)
            target = {
                "user_id": main_user_id,
                "display_name": main_name,
                "panel": "exclude",
            }
            return (
                target,
                hidden,
                no_update,
                hidden,
                no_update,
                _PANEL_OPEN,
                exclude_content,
                "exclude",
            )

        if not user_id:
            raise PreventUpdate
        name = data.user_display(user_id)
        target = {"user_id": user_id, "display_name": name}

        if isinstance(trigger, dict) and trigger.get("type") == "pm-recommend-btn":
            return (
                {**target, "panel": "recommend"},
                _PANEL_OPEN,
                f"Recommend an item for {name}'s network.",
                hidden,
                no_update,
                hidden,
                no_update,
                "recommend",
            )
        if isinstance(trigger, dict) and trigger.get("type") == "pm-forward-btn":
            return (
                {**target, "panel": "forward"},
                hidden,
                no_update,
                _PANEL_OPEN,
                f"Forward {name}'s profile, connections, and context to marketing.",
                hidden,
                no_update,
                "forward",
            )
        raise PreventUpdate

    @app.callback(
        Output(IDs.PM_RECOMMEND_PANEL, "style", allow_duplicate=True),
        Output(IDs.PM_FEEDBACK, "children"),
        Output(IDs.PM_ITEM_DROPDOWN, "value"),
        Output(IDs.PM_RECOMMEND_TEXT, "value"),
        Input(IDs.PM_SEND_RECOMMEND, "n_clicks"),
        State(IDs.PM_TARGET_USER, "data"),
        State(IDs.PM_ITEM_DROPDOWN, "value"),
        prevent_initial_call=True,
    )
    def send_recommendation(_n, target, item):
        if not target or not item:
            raise PreventUpdate
        hidden = {**_PANEL_HIDDEN, **_PANEL_CARD}
        return hidden, success_message("Items recommended to user's network."), None, ""

    @app.callback(
        Output(IDs.PM_FORWARD_PANEL, "style", allow_duplicate=True),
        Output(IDs.PM_FEEDBACK, "children", allow_duplicate=True),
        Output(IDs.PM_MARKETING_TEXT, "value"),
        Input(IDs.PM_SEND_FORWARD, "n_clicks"),
        State(IDs.PM_TARGET_USER, "data"),
        prevent_initial_call=True,
    )
    def send_forward(_n, target):
        if not target:
            raise PreventUpdate
        hidden = {**_PANEL_HIDDEN, **_PANEL_CARD}
        return (
            hidden,
            success_message(
                "Success, comments and user list and connections have been forwarded to marketing."
            ),
            "",
        )

    @app.callback(
        Output(IDs.PM_EXCLUDE_PANEL, "style", allow_duplicate=True),
        Output(IDs.PM_FEEDBACK, "children", allow_duplicate=True),
        Output(IDs.EXCLUDE_LIST_STORE, "data"),
        Input(IDs.PM_CONFIRM_EXCLUDE, "n_clicks"),
        State(IDs.PM_TARGET_USER, "data"),
        State(IDs.PM_EXCLUDE_TESTS, "value"),
        State(IDs.PM_EXCLUDE_CONNECTIONS, "value"),
        State(IDs.EXCLUDE_LIST_STORE, "data"),
        prevent_initial_call=True,
    )
    def confirm_exclude(_n, target, selected_tests, selected_connections, entries):
        if not target or not selected_tests or not selected_connections:
            raise PreventUpdate

        main_user_id = target.get("user_id")
        entries = list(entries or [])
        tests = list(selected_tests)
        for user_id in selected_connections:
            if any(e.get("user_id") == user_id for e in entries):
                continue
            strength = None
            for conn in data.ab_contamination_connections(main_user_id)[0]:
                if conn["user_id"] == user_id:
                    strength = conn["strength"]
                    break
            entries.append(
                {
                    "user_id": user_id,
                    "display_name": data.user_display(user_id),
                    "tests": tests,
                    "main_user_id": main_user_id,
                    "strength": strength,
                }
            )

        hidden = {**_PANEL_HIDDEN, **_PANEL_CARD}
        msg = success_message(
            f"Success, these users will be excluded from A/B testing involving main user, {main_user_id}."
        )
        return hidden, msg, entries

    @app.callback(
        Output(IDs.EXCLUDE_LIST_STORE, "data", allow_duplicate=True),
        Input({"type": "pm-exclude-remove", "user": ALL}, "n_clicks"),
        State(IDs.EXCLUDE_LIST_STORE, "data"),
        prevent_initial_call=True,
    )
    def remove_from_exclude_list(_remove_clicks, entries):
        trigger = ctx.triggered_id
        if not isinstance(trigger, dict) or trigger.get("type") != "pm-exclude-remove":
            raise PreventUpdate
        user_id = trigger.get("user")
        entries = [e for e in list(entries or []) if e.get("user_id") != user_id]
        return entries

    @app.callback(
        Output(IDs.EXCLUDE_LIST_PANEL, "children"),
        Input(IDs.EXCLUDE_LIST_STORE, "data"),
        Input(IDs.ACTIVE_TAB, "value"),
    )
    def render_exclude_list(entries, tab):
        if tab != "alerts":
            return []
        return build_exclude_list_panel(list(entries or []))

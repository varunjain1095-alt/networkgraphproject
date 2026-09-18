"""PM action UI components."""

from __future__ import annotations

from dash import dcc, html

from dashboard.ids import IDs

_BTN = {
    "fontSize": "0.82rem",
    "padding": "0.4rem 0.65rem",
    "marginRight": "0.45rem",
    "marginBottom": "0.35rem",
    "cursor": "pointer",
    "border": "1px solid #cbd5e1",
    "borderRadius": "6px",
    "background": "#ffffff",
}

_PANEL_CARD = {
    "marginTop": "0.75rem",
    "padding": "1rem",
    "border": "1px solid #e2e8f0",
    "borderRadius": "8px",
    "background": "#ffffff",
    "boxShadow": "0 2px 8px rgba(15, 23, 42, 0.06)",
}

_PANEL_HIDDEN = {"display": "none"}


def pm_action_buttons(source: str) -> html.Div:
    return html.Div(
        [
            html.Button(
                "Recommend item to user's network",
                id={"type": "pm-recommend-btn", "source": source},
                n_clicks=0,
                style=_BTN,
            ),
            html.Button(
                "Forward to marketing team",
                id={"type": "pm-forward-btn", "source": source},
                n_clicks=0,
                style=_BTN,
            ),
        ],
        style={"marginTop": "0.5rem"},
    )


def pm_actions_section(source: str, user_label: str | None = None) -> html.Div:
    return html.Div(
        [
            html.H5("PM actions", style={"fontSize": "0.9rem", "margin": "0.75rem 0 0.35rem"}),
            pm_action_buttons(source),
        ],
        style={"borderTop": "1px solid #e2e8f0", "paddingTop": "0.25rem"},
    )


def ab_exclude_button(source: str, user_id: str, flag_label: str) -> html.Button:
    return html.Button(
        "Review users to exclude from testing",
        id={"type": "pm-exclude-btn", "source": source, "user": user_id},
        n_clicks=0,
        style={**_BTN, "marginTop": "0.45rem", "display": "block"},
    )


def success_message(text: str) -> html.Div:
    return html.Div(
        text,
        style={
            "color": "#15803d",
            "background": "#f0fdf4",
            "border": "1px solid #bbf7d0",
            "borderRadius": "6px",
            "padding": "0.55rem 0.75rem",
            "marginTop": "0.5rem",
            "fontSize": "0.88rem",
        },
    )


def build_pm_stores() -> list:
    return [
        dcc.Store(id=IDs.PM_TARGET_USER, data=None),
        dcc.Store(id=IDs.PM_ACTIVE_PANEL, data=None),
        dcc.Store(id=IDs.EXCLUDE_LIST_STORE, data=[]),
    ]


def build_pm_panel_area(item_options: list[dict]) -> html.Div:
    """Non-blocking inline action panels below the graph (not full-screen modals)."""
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.H4("Recommend item to network", style={"margin": 0}),
                            html.Button("×", id=IDs.PM_CLOSE_RECOMMEND, n_clicks=0, style={
                                "border": "none", "background": "none", "fontSize": "1.25rem",
                                "cursor": "pointer", "color": "#64748b", "lineHeight": 1,
                            }),
                        ],
                        style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"},
                    ),
                    html.P(id=IDs.PM_RECOMMEND_USER_LABEL, style={"fontSize": "0.9rem", "color": "#475569", "margin": "0.35rem 0"}),
                    html.Label("Select item", style={"fontSize": "0.85rem"}),
                    dcc.Dropdown(id=IDs.PM_ITEM_DROPDOWN, options=item_options, placeholder="Choose an item..."),
                    html.Label("Add comments", style={"fontSize": "0.85rem", "marginTop": "0.65rem", "display": "block"}),
                    dcc.Textarea(
                        id=IDs.PM_RECOMMEND_TEXT,
                        placeholder="Optional note about why this item fits this user's network...",
                        style={"width": "100%", "minHeight": "80px", "marginTop": "0.35rem"},
                    ),
                    html.Div(style={"height": "0.65rem"}),
                    html.Button("Send recommendations", id=IDs.PM_SEND_RECOMMEND, n_clicks=0, style=_BTN),
                ],
                id=IDs.PM_RECOMMEND_PANEL,
                style={**_PANEL_HIDDEN, **_PANEL_CARD},
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.H4("Forward to marketing team", style={"margin": 0}),
                            html.Button("×", id=IDs.PM_CLOSE_FORWARD, n_clicks=0, style={
                                "border": "none", "background": "none", "fontSize": "1.25rem",
                                "cursor": "pointer", "color": "#64748b", "lineHeight": 1,
                            }),
                        ],
                        style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"},
                    ),
                    html.P(id=IDs.PM_FORWARD_USER_LABEL, style={"fontSize": "0.9rem", "color": "#475569", "margin": "0.35rem 0"}),
                    html.Label("Add comments for marketing team", style={"fontSize": "0.85rem"}),
                    dcc.Textarea(
                        id=IDs.PM_MARKETING_TEXT,
                        placeholder="Add context for the marketing handoff...",
                        style={"width": "100%", "minHeight": "100px", "marginTop": "0.35rem"},
                    ),
                    html.Div(style={"height": "0.65rem"}),
                    html.Button("Send", id=IDs.PM_SEND_FORWARD, n_clicks=0, style=_BTN),
                ],
                id=IDs.PM_FORWARD_PANEL,
                style={**_PANEL_HIDDEN, **_PANEL_CARD},
            ),
            html.Div(
                id=IDs.PM_EXCLUDE_PANEL,
                style={**_PANEL_HIDDEN, **_PANEL_CARD},
            ),
        ],
        id=IDs.PM_PANELS_AREA,
    )


def build_exclude_panel_content(
    main_user_id: str,
    main_name: str,
    connections: list[dict],
    tests: list[str],
) -> list:
    """Build exclude panel with test checkboxes and connected-user checkboxes."""
    test_options = [{"label": test, "value": test} for test in tests]
    conn_options = [
        {
            "label": f"{c['display_name']} ({c['user_id']}) — strength {c['strength']:.2f}",
            "value": c["user_id"],
        }
        for c in connections
    ]

    children: list = [
        html.Div(
            [
                html.H4("Exclude from testing", style={"margin": 0}),
                html.Button("×", id=IDs.PM_CLOSE_EXCLUDE, n_clicks=0, style={
                    "border": "none", "background": "none", "fontSize": "1.25rem",
                    "cursor": "pointer", "color": "#64748b", "lineHeight": 1,
                }),
            ],
            style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"},
        ),
        html.P(
            f"Review contamination connections for {main_name} ({main_user_id}). "
            "Select which tests and connected users to exclude.",
            style={"fontSize": "0.88rem", "color": "#475569", "margin": "0.35rem 0 0.65rem"},
        ),
    ]

    if tests:
        children.extend([
            html.Label("Relevant tests", style={"fontSize": "0.85rem", "fontWeight": 600}),
            dcc.Checklist(
                id=IDs.PM_EXCLUDE_TESTS,
                options=test_options,
                value=[tests[0]] if tests else [],
                labelStyle={"display": "block", "fontSize": "0.85rem", "marginBottom": "0.25rem"},
            ),
        ])

    if conn_options:
        children.extend([
            html.Label("Connected users", style={"fontSize": "0.85rem", "fontWeight": 600, "marginTop": "0.65rem"}),
            dcc.Checklist(
                id=IDs.PM_EXCLUDE_CONNECTIONS,
                options=conn_options,
                value=[c["user_id"] for c in connections],
                labelStyle={"display": "block", "fontSize": "0.85rem", "marginBottom": "0.25rem"},
            ),
        ])
    else:
        children.append(html.P("No connected contamination pairs found for this user.", style={"fontSize": "0.85rem"}))

    children.extend([
        html.Div(style={"height": "0.65rem"}),
        html.Button("Confirm exclusions", id=IDs.PM_CONFIRM_EXCLUDE, n_clicks=0, style=_BTN),
    ])
    return children


def build_exclude_list_panel(entries: list[dict]) -> html.Div:
    if not entries:
        return html.Div(
            [
                html.H5("Exclude from testing", style={"fontSize": "0.9rem", "margin": "0.75rem 0 0.35rem"}),
                html.P(
                    "No users excluded yet. Use Review users to exclude from testing on an A/B contamination flag.",
                    style={"fontSize": "0.8rem", "color": "#64748b"},
                ),
            ]
        )

    rows = []
    for entry in entries:
        strength_bit = f", strength {entry['strength']:.2f}" if entry.get("strength") is not None else ""
        rows.append(
            html.Li(
                [
                    html.Strong(entry.get("display_name") or entry.get("user_id")),
                    html.Span(f" ({entry.get('user_id')}{strength_bit})", style={"color": "#64748b", "fontSize": "0.8rem"}),
                    html.Br(),
                    html.Span(
                        f"Tests: {', '.join(entry.get('tests', []))} · Main user: {entry.get('main_user_id', '—')}",
                        style={"fontSize": "0.78rem", "color": "#475569"},
                    ),
                    html.Button(
                        "Remove",
                        id={"type": "pm-exclude-remove", "user": entry["user_id"]},
                        n_clicks=0,
                        style={**_BTN, "marginLeft": "0.5rem", "padding": "0.15rem 0.45rem", "fontSize": "0.75rem"},
                    ),
                ],
                style={"marginBottom": "0.5rem"},
            )
        )

    return html.Div(
        [
            html.H5("Exclude from testing", style={"fontSize": "0.9rem", "margin": "0.75rem 0 0.35rem"}),
            html.Ul(rows, style={"paddingLeft": "1.1rem", "margin": 0}),
        ],
        style={"borderTop": "1px solid #e2e8f0", "paddingTop": "0.25rem"},
    )

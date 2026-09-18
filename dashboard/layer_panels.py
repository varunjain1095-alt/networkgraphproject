"""Non-graph layer content panels."""

from __future__ import annotations

from dash import html

from dashboard.data_loader import DashboardData


def _heatmap_color(value: float, max_value: float) -> str:
    if max_value <= 0:
        return "#f8fafc"
    intensity = min(1.0, value / max_value)
    alpha = 0.15 + intensity * 0.75
    return f"rgba(34, 197, 94, {alpha:.2f})"


def _coownership_matrix(data: DashboardData, user_id: str | None, limit: int = 5) -> tuple[list[str], dict[tuple[str, str], int]]:
    if not user_id or data.layer3_items.empty:
        return [], {}

    name = data.user_display(user_id)
    user_rows = data.layer3_items[data.layer3_items["display_name"] == name]
    if user_rows.empty:
        return [], {}

    top_items = user_rows.sort_values("usage_total", ascending=False)["item"].drop_duplicates().head(limit).tolist()
    if len(top_items) < 2:
        return top_items, {}

    by_user = data.layer3_items.groupby("display_name")["item"].apply(set)
    matrix: dict[tuple[str, str], int] = {}
    for i, item_a in enumerate(top_items):
        for j, item_b in enumerate(top_items):
            if j < i:
                continue
            count = sum(1 for items in by_user if item_a in items and item_b in items)
            matrix[(item_a, item_b)] = count
            if item_a != item_b:
                matrix[(item_b, item_a)] = count
    return top_items, matrix


def build_ownership_intro(data: DashboardData, user_id: str | None) -> list:
    name = data.user_display(user_id) if user_id else None
    rows = data.layer3_for_user(user_id)
    item_count = len({row.get("item") for row in rows if row.get("item")})

    if user_id and name:
        heading = html.H4(f"Ownership profile: {name}", style={"marginTop": 0})
        if item_count:
            detail = html.P(
                f"Showing {item_count} tracked items for this user, ranked by usage. "
                "Compare against the co-ownership grid to see taste overlap with the broader population.",
                style={"color": "#64748b", "fontSize": "0.9rem"},
            )
        else:
            detail = html.P(
                "No item interactions found for this user in the current sample. "
                "The table below shows top ownership patterns across the network.",
                style={"color": "#64748b", "fontSize": "0.9rem"},
            )
    else:
        heading = html.H4("Ownership patterns across the network", style={"marginTop": 0})
        detail = html.P(
            "Select a user to filter this view to their items. "
            "The table ranks item interactions; the grid shows which items tend to appear together.",
            style={"color": "#64748b", "fontSize": "0.9rem"},
        )
    return [heading, detail]


def build_coownership_grid(data: DashboardData, user_id: str | None) -> list:
    items, matrix = _coownership_matrix(data, user_id)
    if len(items) < 2 or not matrix:
        return []

    max_count = max(matrix.values()) if matrix else 0
    short = {item: (item[:18] + "…" if len(item) > 18 else item) for item in items}

    header = html.Tr([html.Th("", style={"padding": "4px"})] + [
        html.Th(short[item], title=item, style={"fontSize": "0.75rem", "padding": "4px", "maxWidth": "90px"})
        for item in items
    ])
    body_rows = []
    for row_item in items:
        cells = [html.Th(short[row_item], title=row_item, style={"fontSize": "0.75rem", "padding": "4px"})]
        for col_item in items:
            count = matrix.get((row_item, col_item), 0)
            cells.append(
                html.Td(
                    str(count),
                    title=f"{count} users own or use both",
                    style={
                        "textAlign": "center",
                        "fontSize": "0.8rem",
                        "padding": "6px",
                        "background": _heatmap_color(count, max_count),
                        "border": "1px solid #e2e8f0",
                    },
                )
            )
        body_rows.append(html.Tr(cells))

    return [
        html.H5("Items frequently owned together", style={"marginTop": "1rem", "marginBottom": "0.35rem"}),
        html.P(
            "Darker cells mean more users share both items. This highlights taste overlap, not social ties.",
            style={"fontSize": "0.85rem", "color": "#64748b", "marginTop": 0},
        ),
        html.Table(
            [html.Thead(header), html.Tbody(body_rows)],
            style={"borderCollapse": "collapse", "width": "100%", "marginTop": "0.5rem"},
        ),
    ]

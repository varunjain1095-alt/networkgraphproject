"""Explainability panel content builder."""

from __future__ import annotations

from dash import html

from dashboard.data_loader import DashboardData
from dashboard.explainability_display import (
    format_layer_breakdown_plain,
    group_related_flags,
    prediction_plain_summary,
    related_flag_blocks,
    sanitize_display_text,
)
from dashboard.layer_copy import layer_graph_intro, layer_user_summary, layer_why_this_matters
from dashboard.layer_contributions import compute_layer_contributions
from use_cases.base import UseCaseResult


def _details_block(summary: str, body_lines: list[str]) -> html.Details | None:
    lines = [line for line in body_lines if line and str(line).strip()]
    if not lines:
        return None
    return html.Details(
        [
            html.Summary(summary, style={"fontSize": "0.85rem", "color": "#2563eb", "cursor": "pointer"}),
            html.Ul([html.Li(line) for line in lines], style={"marginTop": "0.35rem", "fontSize": "0.9rem"}),
        ],
        style={"marginTop": "0.35rem"},
    )


def build_explanation(
    data: DashboardData,
    user_id: str | None,
    layer: str,
    use_case_result: UseCaseResult | None = None,
) -> list:
    if not user_id:
        return [
            html.P(layer_graph_intro(layer), style={"color": "#64748b"}),
            html.P("Select a user from the ranked list, search, alerts, or a use case to see details."),
        ]

    name = data.user_display(user_id)
    row = data.ranked_users[data.ranked_users["user_id"] == user_id]
    user_row = row.iloc[0] if not row.empty else None

    summary_block = [
        html.H4(name),
        html.P(layer_user_summary(name, layer, user_row)),
        html.P(layer_graph_intro(layer), style={"color": "#64748b", "fontSize": "0.9rem"}),
    ]

    prediction_block: list = []
    if not data.predictions.empty:
        user_preds = data.predictions[data.predictions["user_id"] == user_id].copy()
        if not user_preds.empty:
            user_preds = user_preds.sort_values(
                by=["confidence", "score"],
                ascending=[False, False],
            )
            plain_lines = []
            detail_lines = []
            for _, prow in user_preds.head(5).iterrows():
                score = float(prow.get("score", 0) or 0)
                conf = float(prow.get("confidence", 0) or 0)
                target = prow.get("target_id") or None
                if target in (None, "\u2014", "-"):
                    target = None
                ptype = str(prow.get("prediction_type", "prediction"))
                plain_lines.append(prediction_plain_summary(ptype, score, conf, target))
                target_bit = f", related to {target}" if target else ""
                detail_lines.append(
                    f"{ptype.replace('_', ' ').title()}: score {score:.0%}, confidence {conf:.0%}{target_bit}"
                )

            prediction_block = [
                html.H5("Forward-looking predictions"),
                html.P(plain_lines[0], style={"fontWeight": 500}),
            ]
            if len(plain_lines) > 1:
                prediction_block.extend([html.P(line) for line in plain_lines[1:]])
            details = _details_block("Show exact prediction scores", detail_lines)
            if details is not None:
                prediction_block.append(details)

            if not row.empty:
                contributions = compute_layer_contributions(row.iloc[0], data.predictions, user_id)
                lead, breakdown_lines, details = format_layer_breakdown_plain(contributions)
                prediction_block.extend(
                    [
                        html.Hr(style={"margin": "0.75rem 0"}),
                        html.H5("Why this matters"),
                        html.P(lead),
                        html.Ul([html.Li(line) for line in breakdown_lines]),
                    ]
                )
                layer_details = _details_block("Show exact layer percentages", [details] if details else [])
                if layer_details is not None:
                    prediction_block.append(layer_details)
    else:
        prediction_block = [
            html.H5("Why this matters"),
            html.P(layer_why_this_matters(name, layer)),
        ]

    grouped = group_related_flags(data.use_case_results, user_id)
    related_block: list = []
    if grouped:
        related_block = [
            html.H5("Related use case flags"),
            html.Ul(related_flag_blocks(grouped, user_id), style={"paddingLeft": "1.2rem"}),
        ]

    uc_block: list = []
    if use_case_result:
        match = next((f for f in use_case_result.flagged if f.node_id == user_id), None)
        if not match and "|" in (use_case_result.flagged[0].node_id if use_case_result.flagged else ""):
            match = next(
                (f for f in use_case_result.flagged if user_id in f.node_id.split("|", 1)),
                None,
            )
        if match:
            uc_block = [
                html.Hr(),
                html.H5(f"Active use case: {use_case_result.title}"),
                html.P(sanitize_display_text(match.explanation)),
                html.P([html.B("Recommended action: "), sanitize_display_text(match.recommended_action)]),
            ]

    return [
        *summary_block,
        html.Hr(style={"margin": "0.75rem 0"}),
        *prediction_block,
        *related_block,
        *uc_block,
    ]

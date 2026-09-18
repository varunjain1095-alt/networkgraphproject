"""Contextual alerts card shown beside the graph on the Alerts tab."""

from __future__ import annotations

from collections import defaultdict

from dash import html

from dashboard.data_loader import DashboardData
from dashboard.explainability_display import sanitize_display_text, summarize_use_case_flags
from dashboard.pm_actions import ab_exclude_button, pm_actions_section
from use_cases.base import FlaggedItem

ALERTS_COLUMN_VISIBLE = {
    "display": "block",
    "width": "38%",
    "minWidth": "260px",
    "maxWidth": "340px",
    "flexShrink": 0,
    "height": "600px",
    "overflowY": "auto",
    "padding": "1rem",
    "border": "1px solid #e2e8f0",
    "borderRadius": "8px",
    "background": "#ffffff",
}

ALERTS_COLUMN_HIDDEN = {"display": "none"}


def _pm_why_it_matters(use_case_id: str, item: FlaggedItem) -> str:
    """Short product-manager framing for a specific flag."""
    templates = {
        "onboarding_flow": (
            "Onboarding path affects early retention and support load. "
            "Mis-routed users often churn before they find value."
        ),
        "discovery_gap": (
            "Low exposure in this cluster can look like poor engagement in analytics. "
            "Check reach before changing the feature."
        ),
        "fraud_detection": (
            "Coordinated clusters can skew metrics and abuse promotions. "
            "Investigate before trusting conversion or referral numbers from this group."
        ),
        "rollout_sequencing": (
            "Seeding with well-connected users improves early adoption signal "
            "and reduces time to meaningful experiment readouts."
        ),
        "support_escalation": (
            "Bridging users amplify negative word of mouth when support slips. "
            "Prioritize resolution to limit downstream churn."
        ),
        "ab_contamination": (
            "Connected users in different test arms can leak treatment effects "
            "and invalidate experiment conclusions."
        ),
        "champion_churn": (
            "Losing a super-connector can trigger follow-on disengagement in their cluster. "
            "Retention here protects broader active-user counts."
        ),
        "research_priority": (
            "High community-validated users represent peer opinion, not just individual preference. "
            "Their feedback is efficient for research sampling."
        ),
    }
    if use_case_id in templates:
        return sanitize_display_text(templates[use_case_id])
    if item.recommended_action:
        return sanitize_display_text(f"Suggested follow-up: {item.recommended_action}")
    return sanitize_display_text("Review this flag and decide whether product or ops action is needed.")


def _use_case_block(use_case_id: str, title: str, items: list[FlaggedItem], user_id: str) -> html.Div:
    summary, details = summarize_use_case_flags(title, items, user_id)
    primary = max(items, key=lambda item: item.score)

    children: list = [
        html.Div(title, style={"fontWeight": 600, "fontSize": "0.92rem", "marginBottom": "0.35rem"}),
        html.P(
            summary,
            style={"fontSize": "0.88rem", "margin": "0 0 0.45rem 0", "lineHeight": "1.45"},
        ),
        html.P(
            _pm_why_it_matters(use_case_id, primary),
            style={
                "fontSize": "0.8rem",
                "color": "#475569",
                "margin": 0,
                "padding": "0.45rem 0.55rem",
                "background": "#f8fafc",
                "borderRadius": "4px",
            },
        ),
    ]
    if details:
        children.append(
            html.Details(
                [
                    html.Summary(
                        f"Show {len(details)} individual instances",
                        style={"fontSize": "0.85rem", "color": "#2563eb", "cursor": "pointer", "marginTop": "0.45rem"},
                    ),
                    html.Ul(
                        [html.Li(line) for line in details],
                        style={"marginTop": "0.35rem", "paddingLeft": "1.1rem", "fontSize": "0.85rem"},
                    ),
                ],
                style={"marginTop": "0.35rem"},
            )
        )
    if use_case_id == "ab_contamination":
        children.append(ab_exclude_button("alerts", user_id, title))

    return html.Div(
        children,
        style={"marginBottom": "0.85rem", "paddingBottom": "0.85rem", "borderBottom": "1px solid #e2e8f0"},
    )


def build_alerts_context_card(data: DashboardData, user_id: str | None) -> list:
    if not user_id:
        return []

    flags = data.flags_for_user(user_id)
    if not flags:
        return [
            html.Div(
                data.user_display(user_id),
                style={"fontWeight": 600, "fontSize": "0.95rem", "marginBottom": "0.35rem"},
            ),
            html.P(
                "This user is not flagged in the current alert sample.",
                style={"fontSize": "0.88rem", "color": "#64748b", "margin": 0},
            ),
        ]

    grouped: dict[str, list[FlaggedItem]] = defaultdict(list)
    titles: dict[str, str] = {}
    for uc_id, title, item in flags:
        grouped[uc_id].append(item)
        titles[uc_id] = title

    name = data.user_display(user_id)
    use_case_count = len(grouped)
    signal_count = len(flags)
    count_line = f"Flagged in {use_case_count} use case{'s' if use_case_count != 1 else ''}"
    if signal_count > use_case_count:
        count_line += f" ({signal_count} total signals)"

    blocks = [_use_case_block(uc_id, titles[uc_id], items, user_id) for uc_id, items in grouped.items()]

    return [
        html.Div(name, style={"fontWeight": 600, "fontSize": "0.95rem", "marginBottom": "0.15rem"}),
        html.P(count_line, style={"fontSize": "0.78rem", "color": "#64748b", "margin": "0 0 0.65rem 0"}),
        *blocks,
        pm_actions_section("alerts", name),
    ]

"""Plain-language formatting for the explainability panel (display only)."""

from __future__ import annotations

import re
from collections import defaultdict

from dash import html

from use_cases.base import FlaggedItem

FORBIDDEN_DASHES = ("\u2014", "\u2013")  # em dash, en dash


def sanitize_display_text(text: str) -> str:
    """Replace em/en dashes in user-facing copy with natural punctuation."""
    if not text:
        return text
    if not any(dash in text for dash in FORBIDDEN_DASHES):
        return text
    # Label or title before a descriptor: use a colon.
    text = re.sub(r"(\w)\s*[\u2014\u2013]\s+(?=[a-z])", r"\1: ", text)
    # Remaining clause joins: use a comma.
    text = re.sub(r"\s*[\u2014\u2013]\s+", ", ", text)
    return text

LAYER_DISPLAY_NAMES = {
    "layer1": "Relationships",
    "layer2": "Shared activity",
    "layer3": "Ownership patterns",
    "layer4": "Reviews and curators",
    "all": "Relationships",
}

LAYER_VIEW_PHRASES = {
    "layer1": "Currently viewing their direct connections through relationships.",
    "layer2": "Currently viewing their shared activity network.",
    "layer3": "Currently viewing their ownership patterns and item interactions.",
    "layer4": "Currently viewing their reviews and curator connections.",
    "all": "Currently viewing their direct connections (relationships overview).",
}

CONTRIBUTION_LABEL_MAP = {
    "Layer 1 — Relationships": "Relationships",
    "Layer 2 — Shared activity": "Shared activity",
    "Layer 3 — User–item": "Ownership patterns",
    "Layer 4 — Influence": "Reviews and curators",
}

PREDICTION_TYPE_LABELS = {
    "adoption": "Product adoption",
    "churn_cascade": "Churn cascade risk",
    "influence_propagation": "Influence spread",
}


def influence_sentence(name: str, rank: int | None, total: int, percentile: str | None) -> str:
    if rank is None or total <= 0:
        return sanitize_display_text(
            f"{name} plays a meaningful role in how information and behavior move through this network."
        )
    share = rank / total
    percentile_text = percentile or f"top {max(1, int(share * 100))}%"
    if share <= 0.01:
        return sanitize_display_text(
            f"{name} is one of the most influential people in this network, "
            f"{percentile_text} for how central and connected they are."
        )
    if share <= 0.05:
        return sanitize_display_text(
            f"{name} is highly influential in this network, "
            f"well above average for centrality and connections ({percentile_text})."
        )
    if share <= 0.15:
        return sanitize_display_text(
            f"{name} has above-average influence in this network. "
            f"Their position helps shape how activity spreads ({percentile_text})."
        )
    if share <= 0.35:
        return sanitize_display_text(
            f"{name} has moderate influence in this network, "
            f"connected enough to matter, but not among the most central members."
        )
    return sanitize_display_text(
        f"{name} has a more peripheral position in this network, "
        f"still connected, but with less structural pull than top-ranked members."
    )


def layer_view_phrase(layer: str) -> str:
    return sanitize_display_text(LAYER_VIEW_PHRASES.get(layer, LAYER_VIEW_PHRASES["layer1"]))


def confidence_phrase(value: float) -> str:
    if value >= 0.75:
        return "high confidence"
    if value >= 0.5:
        return "moderate confidence"
    if value >= 0.25:
        return "lower confidence"
    return "very low confidence"


def signal_strength_phrase(score: float) -> str:
    if score >= 0.7:
        return "strong signal"
    if score >= 0.5:
        return "moderate signal"
    if score >= 0.3:
        return "emerging signal"
    return "weak signal"


def contribution_strength_phrase(share: float) -> str:
    if share >= 0.45:
        return "primary driver"
    if share >= 0.28:
        return "major contributor"
    if share >= 0.15:
        return "supporting factor"
    return "minor factor"


def plain_layer_name(internal_label: str) -> str:
    return CONTRIBUTION_LABEL_MAP.get(internal_label, internal_label)


def format_layer_breakdown_plain(contributions: list[tuple[str, float]]) -> tuple[str, list[str], str]:
    if not contributions:
        return (
            "We do not yet have enough signal to explain which network layers drive this profile.",
            [],
            "",
        )
    top_label, top_share = contributions[0]
    top_plain = plain_layer_name(top_label)
    lead = (
        f"{top_plain} is the strongest driver of this person's influence profile "
        f"({contribution_strength_phrase(top_share)})."
    )
    lines = [
        f"{plain_layer_name(label)}: {contribution_strength_phrase(share)}"
        for label, share in contributions
        if share > 0
    ]
    details = " · ".join(
        f"{plain_layer_name(label)}: {share:.0%}" for label, share in contributions if share > 0
    )
    return sanitize_display_text(lead), [sanitize_display_text(line) for line in lines], sanitize_display_text(details)


def prediction_plain_summary(prediction_type: str, score: float, confidence: float, target: str | None) -> str:
    label = PREDICTION_TYPE_LABELS.get(prediction_type, prediction_type.replace("_", " ").title())
    parts = [f"{label}: {signal_strength_phrase(score)}, {confidence_phrase(confidence)}"]
    if target and target != "\u2014":
        parts.append(f"related to {target}")
    return sanitize_display_text(", ".join(parts))


def item_involves_user(item: FlaggedItem, user_id: str) -> bool:
    if item.node_id == user_id:
        return True
    if item.extra.get("user_id_b") == user_id:
        return True
    if "|" in item.node_id:
        left, right = item.node_id.split("|", 1)
        if user_id in (left, right):
            return True
    return False


def _strength_value(item: FlaggedItem) -> float:
    if "combined_strength" in item.metrics:
        return float(item.metrics["combined_strength"])
    return float(item.score)


def summarize_use_case_flags(title: str, items: list[FlaggedItem], user_id: str) -> tuple[str, list[str]]:
    """Return a summary line and optional detail lines for related use-case flags."""
    if len(items) == 1:
        return sanitize_display_text(items[0].explanation), []

    if title.lower().startswith("a/b test"):
        strengths = [_strength_value(item) for item in items]
        detail_lines = [sanitize_display_text(item.explanation) for item in items]
        summary = sanitize_display_text(
            f"A/B test contamination: connected to {len(items)} other users in different test groups, "
            f"strength range {min(strengths):.2f} to {max(strengths):.2f}."
        )
        return summary, detail_lines

    detail_lines = [sanitize_display_text(item.explanation) for item in items]
    summary = sanitize_display_text(f"{title}: {len(items)} related signals flagged for this user.")
    return summary, detail_lines


def related_flag_blocks(
    grouped: dict[str, list[FlaggedItem]],
    user_id: str,
) -> list:
    blocks: list = []
    for title, items in grouped.items():
        summary, details = summarize_use_case_flags(title, items, user_id)
        if details:
            blocks.append(
                html.Li(
                    [
                        summary,
                        html.Details(
                            [
                                html.Summary(
                                    f"Show {len(details)} individual flags",
                                    style={"fontSize": "0.85rem", "color": "#2563eb", "cursor": "pointer"},
                                ),
                                html.Ul([html.Li(line) for line in details], style={"marginTop": "0.35rem"}),
                            ],
                            style={"marginTop": "0.25rem"},
                        ),
                    ],
                    style={"marginBottom": "0.5rem"},
                )
            )
        else:
            blocks.append(html.Li(summary, style={"marginBottom": "0.5rem"}))
    return blocks


def group_related_flags(
    use_case_results: dict,
    user_id: str,
) -> dict[str, list[FlaggedItem]]:
    grouped: dict[str, list[FlaggedItem]] = defaultdict(list)
    for result in use_case_results.values():
        for item in result.flagged:
            if item_involves_user(item, user_id):
                grouped[result.title].append(item)
    return dict(grouped)

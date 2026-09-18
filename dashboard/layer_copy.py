"""Layer-specific copy for graph intros and explainability."""

from __future__ import annotations

import pandas as pd

from dashboard.explainability_display import sanitize_display_text

LAYER_GRAPH_INTROS = {
    "layer1": (
        "Relationships map who knows whom. Each node is a person; lines are direct ties. "
        "The green node is the selected user. Hover for details, click to pin a name label."
    ),
    "layer2": (
        "Shared activity maps co-play and joint usage. Lines mean people participated in the "
        "same sessions or activities, weighted by how often they overlap. "
        "Hover for details, click to pin a name label."
    ),
    "layer3": (
        "Ownership patterns work differently from the other layers. There is no connected network "
        "view here because shared ownership and taste similarity are better shown as rankings "
        "and comparisons. Use the table below to see which items a user engages with and how "
        "their taste compares to others."
    ),
    "layer4": (
        "Reviews and curators map trust and influence beyond direct friendships. "
        "Green is the selected user. Blue nodes are other people, orange are trusted sources, "
        "purple are contributions, and gray are items. Lines show follows, validations, "
        "and recommendations."
    ),
}


def layer_graph_intro(layer: str) -> str:
    if layer == "all":
        layer = "layer1"
    return sanitize_display_text(LAYER_GRAPH_INTROS.get(layer, LAYER_GRAPH_INTROS["layer1"]))


def _metric(row: pd.Series, *columns: str) -> float | None:
    for col in columns:
        if col in row.index and pd.notna(row[col]):
            return float(row[col])
    return None


def layer_user_summary(name: str, layer: str, row: pd.Series | None) -> str:
    if row is None or (hasattr(row, "empty") and row.empty):
        return sanitize_display_text(f"Select {name} to see how they appear in this layer.")

    if layer == "all":
        layer = "layer1"
    if layer in ("layer1",):
        degree = _metric(row, "layer1_degree")
        betweenness = _metric(row, "layer1_betweenness")
        parts = [f"In relationships, {name}"]
        if degree is not None:
            parts.append(f"has {int(degree)} direct ties")
        if betweenness is not None and betweenness >= 0.01:
            parts.append("and often sits on paths between groups, acting as a bridge")
        elif betweenness is not None:
            parts.append("and is mostly embedded within their own cluster")
        return sanitize_display_text(", ".join(parts) + ".")

    if layer == "layer2":
        degree = _metric(row, "layer2_degree")
        community = row.get("layer2_community_id") if "layer2_community_id" in row.index else None
        text = f"In shared activity, {name}"
        if degree is not None:
            text += f" co-participates with {int(degree)} other people through sessions and joint usage"
        else:
            text += " appears in the shared activity graph through co-play patterns"
        if pd.notna(community):
            text += f", grouped with others who share similar activity habits (cluster {int(community)})"
        return sanitize_display_text(text + ".")

    if layer == "layer3":
        degree = _metric(row, "layer3_degree")
        text = f"For ownership patterns, {name}"
        if degree is not None:
            text += f" is linked to {int(degree)} items through purchases, usage, or saves"
        else:
            text += " is profiled by item interactions rather than social ties"
        text += ". Similarity comes from overlapping item choices, not from who they know."
        return sanitize_display_text(text + ".")

    if layer == "layer4":
        degree = _metric(row, "layer4_degree")
        eigen = _metric(row, "layer4_eigenvector")
        text = f"In reviews and curators, {name}"
        if degree is not None:
            text += f" connects to {int(degree)} trust and contribution nodes"
        else:
            text += " participates in the curator and validation network"
        if eigen is not None and eigen >= 0.05:
            text += ", with peer-validated influence that can shape what others trust"
        else:
            text += ", mainly consuming and validating others' contributions"
        return sanitize_display_text(text + ".")

    return sanitize_display_text(f"{name} in this layer.")


def layer_why_this_matters(name: str, layer: str) -> str:
    messages = {
        "layer1": (
            f"{name}'s relationship position affects how information, churn risk, and product "
            "issues travel along friend and collaborator ties."
        ),
        "layer2": (
            f"{name}'s shared activity footprint shows who they actually spend time with, "
            "which often differs from declared relationships and predicts co-adoption."
        ),
        "layer3": (
            f"{name}'s ownership pattern helps predict adoption and taste clusters. "
            "Users with overlapping item choices tend to respond similarly to recommendations."
        ),
        "layer4": (
            f"{name}'s curator and review connections shape trust. Validations and follows "
            "here influence which content and recommendations spread beyond direct friends."
        ),
    }
    if layer == "all":
        layer = "layer1"
    return sanitize_display_text(messages.get(layer, messages["layer1"]))

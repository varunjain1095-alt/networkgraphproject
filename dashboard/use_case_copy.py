"""Plain-language use case descriptions for the dashboard."""

from __future__ import annotations

from dashboard.explainability_display import sanitize_display_text

USE_CASE_DESCRIPTIONS: dict[str, str] = {
    "onboarding_flow": (
        "Onboarding flow decisioning recommends whether a new or returning user should get "
        "self-service onboarding or guided onboarding with buddy matching. Users with at least "
        "one active connection on the platform can lean on existing contacts; isolated users "
        "benefit from more hand-holding."
    ),
    "discovery_gap": (
        "Feature discovery gap detection finds communities where too few members have been "
        "exposed to a feature. Low engagement in these clusters may reflect poor reach rather "
        "than poor product fit, so rollout or awareness may be needed before judging performance."
    ),
    "fraud_detection": (
        "Fraud and fake-account ring detection surfaces unusually dense, reciprocal connection "
        "patterns that may indicate coordinated or inorganic behavior. These clusters warrant "
        "trust-and-safety review before taking action."
    ),
    "rollout_sequencing": (
        "Feature rollout sequencing identifies influential, well-connected users who can seed "
        "organic spread when a feature launches. Prioritizing them early improves signal quality "
        "and adoption velocity."
    ),
    "support_escalation": (
        "Support escalation prioritization flags open tickets from users who bridge multiple "
        "groups. A poor experience for these users can ripple outward, so their tickets merit "
        "faster resolution and proactive outreach."
    ),
    "ab_contamination": (
        "A/B test contamination detection finds user pairs who are strongly connected in the "
        "network but assigned to different experiment variants. Connected users can influence "
        "each other's behavior and invalidate experiment results."
    ),
    "champion_churn": (
        "Champion and super-connector churn risk highlights structurally central users who are "
        "still active but whose departure could cascade through their cluster. Retaining them "
        "protects downstream engagement."
    ),
    "research_priority": (
        "User research prioritization surfaces people with high community-validated influence: "
        "peers engage with and validate their contributions. Their feedback often represents "
        "broader community perspective."
    ),
}


def use_case_description(use_case_id: str, title: str = "") -> str:
    if use_case_id in USE_CASE_DESCRIPTIONS:
        return sanitize_display_text(USE_CASE_DESCRIPTIONS[use_case_id])
    if title:
        return sanitize_display_text(f"{title} flags users based on network structure and product signals.")
    return sanitize_display_text("This use case flags users based on network structure and product signals.")


def alerts_overview_text() -> str:
    return sanitize_display_text(
        "Alerts combine the highest-priority flags from every use case. Each row is a user or "
        "pair that triggered a rule. Select a row to read what that use case means and why this "
        "entry was flagged."
    )

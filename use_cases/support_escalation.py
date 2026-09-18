"""Use case #5 — support / moderation escalation."""

from __future__ import annotations

from use_cases.base import BaseUseCase, FlaggedItem, UseCaseResult
from use_cases.context import UseCaseContext
from use_cases.rollout_sequencing import result_sorted


class SupportEscalationUseCase(BaseUseCase):
    use_case_id = "support_escalation"
    title = "Support escalation prioritization"
    supports_toggle = True
    required_layers = ["layer1"]

    def run(self, ctx: UseCaseContext, most_important: bool = True) -> UseCaseResult:
        tickets = ctx.open_support_tickets()
        flagged: list[FlaggedItem] = []

        severity_weight = {"critical": 1.0, "high": 0.8, "medium": 0.5, "low": 0.3}

        for ticket in tickets:
            user_id = ticket["user_id"]
            betweenness = ctx.user_metric(user_id, "layer1", "betweenness")
            sev = ticket.get("severity", "medium")
            score = betweenness * severity_weight.get(sev, 0.5)
            meta = ctx.user_meta(user_id)
            flagged.append(
                FlaggedItem(
                    node_id=user_id,
                    label=meta.get("display_name", user_id),
                    score=score,
                    metrics={"betweenness": betweenness, "severity_weight": severity_weight.get(sev, 0.5)},
                    explanation=(
                        f"Open {sev} ticket from {meta.get('display_name', user_id)}. "
                        "This user bridges multiple groups, so a negative experience may spread widely."
                    ),
                    recommended_action="Prioritize ticket resolution and proactive outreach.",
                    subgraph_center=user_id,
                    extra={"ticket_id": ticket["ticket_id"], "severity": sev},
                )
            )

        if not flagged:
            return UseCaseResult(
                use_case_id=self.use_case_id,
                title=self.title,
                flagged=[],
                empty_message="No open support tickets to prioritize.",
                supports_toggle=self.supports_toggle,
                required_layers=self.required_layers,
            )

        return UseCaseResult(
            use_case_id=self.use_case_id,
            title=self.title,
            flagged=result_sorted(flagged, most_important),
            supports_toggle=self.supports_toggle,
            required_layers=self.required_layers,
        )

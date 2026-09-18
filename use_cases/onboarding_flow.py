"""Use case #6 — onboarding flow decisioning."""

from __future__ import annotations

from use_cases.base import BaseUseCase, FlaggedItem, UseCaseResult
from use_cases.context import UseCaseContext


class OnboardingFlowUseCase(BaseUseCase):
    use_case_id = "onboarding_flow"
    title = "Onboarding flow decisioning"
    supports_toggle = False
    required_layers = ["layer1"]

    def run(self, ctx: UseCaseContext, most_important: bool = True) -> UseCaseResult:
        rows = ctx.conn.execute(
            """
            SELECT user_id, onboarding_flow_type, had_active_connection_at_start, completion_status
            FROM onboarding_events
            ORDER BY assigned_timestamp DESC
            LIMIT 200
            """
        ).fetchall()

        flagged: list[FlaggedItem] = []
        for row in rows:
            user_id = row["user_id"]
            has_active = ctx.has_active_connection(user_id)
            flow = "self_service" if has_active else "guided"
            meta = ctx.user_meta(user_id)
            name = meta.get("display_name", user_id)
            flagged.append(
                FlaggedItem(
                    node_id=user_id,
                    label=name,
                    score=1.0 if has_active else 0.0,
                    metrics={"has_active_connection": float(has_active)},
                    explanation=(
                        f"{name} has an active connection on the platform. Recommend self-service onboarding."
                        if has_active
                        else f"{name} has no active connections. Recommend guided onboarding with buddy matching."
                    ),
                    recommended_action=(
                        "Assign self-service onboarding path."
                        if has_active
                        else "Assign guided onboarding and suggest connecting with an active contact."
                    ),
                    subgraph_center=user_id,
                    extra={"recommended_flow": flow},
                )
            )

        if not flagged:
            return UseCaseResult(
                use_case_id=self.use_case_id,
                title=self.title,
                flagged=[],
                empty_message="No recent onboarding events found.",
                supports_toggle=self.supports_toggle,
                required_layers=self.required_layers,
            )

        return UseCaseResult(
            use_case_id=self.use_case_id,
            title=self.title,
            flagged=flagged,
            supports_toggle=self.supports_toggle,
            required_layers=self.required_layers,
        )

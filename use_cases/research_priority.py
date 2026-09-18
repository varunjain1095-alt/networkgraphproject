"""Use case #4 — user research prioritization."""

from __future__ import annotations

from use_cases.base import BaseUseCase, FlaggedItem, UseCaseResult
from use_cases.context import UseCaseContext
from use_cases.rollout_sequencing import result_sorted


class ResearchPriorityUseCase(BaseUseCase):
    use_case_id = "research_priority"
    title = "User research prioritization"
    supports_toggle = True
    required_layers = ["layer4"]

    def run(self, ctx: UseCaseContext, most_important: bool = True) -> UseCaseResult:
        ranked = ctx.users_with_metric("layer4", "community_validated_influence")
        flagged: list[FlaggedItem] = []

        for user_id, cvi in ranked[:100]:
            if cvi <= 0:
                continue
            degree = ctx.user_metric(user_id, "layer1", "degree")
            meta = ctx.user_meta(user_id)
            flagged.append(
                FlaggedItem(
                    node_id=user_id,
                    label=meta.get("display_name", user_id),
                    score=cvi,
                    metrics={"community_validated_influence": cvi, "degree": degree},
                    explanation=(
                        f"{meta.get('display_name', user_id)} earns high community-validated influence "
                        f"(score {cvi:.2f}). Their peers engage with and validate their contributions."
                    ),
                    recommended_action="Invite to user research; insights likely represent community perspective.",
                    subgraph_center=user_id,
                )
            )

        if not flagged:
            return UseCaseResult(
                use_case_id=self.use_case_id,
                title=self.title,
                flagged=[],
                empty_message="No users with community-validated influence found.",
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

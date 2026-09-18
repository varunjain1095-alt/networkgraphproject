"""Use case #1 — A/B test contamination detection."""

from __future__ import annotations

from use_cases.base import BaseUseCase, FlaggedItem, UseCaseResult
from use_cases.context import UseCaseContext
from use_cases.rollout_sequencing import result_sorted


def contamination_tier(strength: float) -> str:
    if strength >= 0.7:
        return "high"
    if strength >= 0.4:
        return "medium"
    return "low"


class ABContaminationUseCase(BaseUseCase):
    use_case_id = "ab_contamination"
    title = "A/B test contamination detection"
    supports_toggle = True
    required_layers = ["layer1", "layer2"]

    def run(self, ctx: UseCaseContext, most_important: bool = True) -> UseCaseResult:
        pairs = ctx.pairwise_contamination(min_strength=0.2)
        flagged: list[FlaggedItem] = []
        tier_rank = {"high": 3, "medium": 2, "low": 1}

        for pair in pairs:
            strength = pair["combined_strength"]
            tier = contamination_tier(strength)
            user_a, user_b = pair["user_id_a"], pair["user_id_b"]
            meta_a = ctx.user_meta(user_a)
            meta_b = ctx.user_meta(user_b)
            pair_id = f"{user_a}|{user_b}"
            flagged.append(
                FlaggedItem(
                    node_id=pair_id,
                    node_type="pair",
                    score=strength + tier_rank[tier] * 0.01,
                    label=f"{meta_a.get('display_name', user_a)} ↔ {meta_b.get('display_name', user_b)}",
                    metrics={"combined_strength": strength, "tier_rank": float(tier_rank[tier])},
                    explanation=(
                        f"{tier.title()}-risk contamination: {meta_a.get('display_name', user_a)} and "
                        f"{meta_b.get('display_name', user_b)} are connected (strength {strength:.2f}) "
                        f"but assigned to different experiment variants ({', '.join(pair['experiments'])})."
                    ),
                    recommended_action=(
                        "Exclude one or both users from the experiment or re-randomize cohorts."
                        if tier == "high"
                        else "Review experiment assignment; consider excluding strongly connected pairs."
                    ),
                    subgraph_center=user_a,
                    extra={"user_id_b": user_b, "tier": tier, "experiments": pair["experiments"]},
                )
            )

        if not flagged:
            return UseCaseResult(
                use_case_id=self.use_case_id,
                title=self.title,
                flagged=[],
                empty_message="No experiment contamination detected above threshold.",
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

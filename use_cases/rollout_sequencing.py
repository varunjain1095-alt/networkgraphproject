"""Use case #3 — feature rollout sequencing."""

from __future__ import annotations

from use_cases.base import BaseUseCase, FlaggedItem, UseCaseResult
from use_cases.context import UseCaseContext
from use_cases.prediction_scores import forward_adoption_score, prediction_confidence


class RolloutSequencingUseCase(BaseUseCase):
    use_case_id = "rollout_sequencing"
    title = "Feature rollout sequencing"
    supports_toggle = True
    required_layers = ["layer1"]

    def run(self, ctx: UseCaseContext, most_important: bool = True) -> UseCaseResult:
        ranked = ctx.users_with_metric("layer1", "eigenvector")
        flagged: list[FlaggedItem] = []

        for user_id, eigen in ranked[:100]:
            meta = ctx.user_meta(user_id)
            score = eigen
            extra = {}
            forward = forward_adoption_score(user_id)
            explanation = (
                f"{meta.get('display_name', user_id)} is well-connected to other influential users. "
                "Rolling out here first maximizes organic spread and early signal."
            )
            if forward is not None:
                score = eigen * 0.6 + forward * 0.4
                extra["forward_adoption_score"] = forward
                conf = prediction_confidence(user_id, "adoption")
                if conf is not None:
                    extra["prediction_confidence"] = conf
                explanation += f" Predicted adoption likelihood: {forward:.0%}."
            flagged.append(
                FlaggedItem(
                    node_id=user_id,
                    label=meta.get("display_name", user_id),
                    score=score,
                    metrics={"eigenvector": eigen},
                    explanation=explanation,
                    recommended_action="Include in early feature rollout cohort.",
                    subgraph_center=user_id,
                    extra=extra,
                )
            )

        result = UseCaseResult(
            use_case_id=self.use_case_id,
            title=self.title,
            flagged=result_sorted(flagged, most_important),
            supports_toggle=self.supports_toggle,
            required_layers=self.required_layers,
        )
        if not result.flagged:
            result.empty_message = "No users available for rollout ranking."
        return result


def result_sorted(items: list[FlaggedItem], most_important: bool) -> list[FlaggedItem]:
    ordered = sorted(items, key=lambda x: x.score, reverse=most_important)
    for i, item in enumerate(ordered, start=1):
        item.rank = i
    return ordered

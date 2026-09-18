"""Use case #2 — champion / super-connector churn risk."""

from __future__ import annotations

from use_cases.base import BaseUseCase, FlaggedItem, UseCaseResult
from use_cases.context import UseCaseContext
from use_cases.prediction_scores import forward_adoption_score, prediction_confidence, prediction_score
from use_cases.rollout_sequencing import result_sorted


class ChampionChurnUseCase(BaseUseCase):
    use_case_id = "champion_churn"
    title = "Champion / super-connector churn risk"
    supports_toggle = True
    required_layers = ["layer1", "layer2"]

    def run(self, ctx: UseCaseContext, most_important: bool = True) -> UseCaseResult:
        churned = ctx.churned_user_ids()
        active = ctx.active_user_ids()
        flagged: list[FlaggedItem] = []

        for user_id in active:
            if user_id in churned:
                continue
            eigen = ctx.user_metric(user_id, "layer1", "eigenvector")
            activity = ctx.user_metric(user_id, "layer2", "degree")
            activity_norm = min(activity / 50.0, 1.0)
            score = eigen * 0.7 + activity_norm * 0.3
            forward = prediction_score(user_id, "churn_cascade")
            extra = {}
            if forward is not None:
                score = score * 0.65 + forward * 0.35
                extra["forward_cascade_score"] = forward
                conf = prediction_confidence(user_id, "churn_cascade")
                if conf is not None:
                    extra["prediction_confidence"] = conf
            meta = ctx.user_meta(user_id)
            explanation = (
                f"{meta.get('display_name', user_id)} is structurally central and still active. "
                "If they disengage, connected users in their cluster may follow."
            )
            if forward is not None:
                explanation += f" Forward-looking cascade risk score: {forward:.0%}."
            if score < 0.05:
                continue
            flagged.append(
                FlaggedItem(
                    node_id=user_id,
                    label=meta.get("display_name", user_id),
                    score=score,
                    metrics={"eigenvector": eigen, "activity_degree": activity},
                    explanation=explanation,
                    recommended_action="Prioritize retention outreach and monitor cluster engagement.",
                    subgraph_center=user_id,
                    extra=extra,
                )
            )

        flagged = result_sorted(flagged, most_important)[:100]

        if not flagged:
            return UseCaseResult(
                use_case_id=self.use_case_id,
                title=self.title,
                flagged=[],
                empty_message="No high-risk champions identified among active users.",
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

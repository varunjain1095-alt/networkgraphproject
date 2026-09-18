"""Use case #7 — feature discovery gap detection."""

from __future__ import annotations

from use_cases.base import BaseUseCase, FlaggedItem, UseCaseResult
from use_cases.context import UseCaseContext

EXPOSURE_GAP_THRESHOLD = 0.25


class DiscoveryGapUseCase(BaseUseCase):
    use_case_id = "discovery_gap"
    title = "Feature discovery gap detection"
    supports_toggle = False
    required_layers = ["layer2"]

    def run(self, ctx: UseCaseContext, most_important: bool = True) -> UseCaseResult:
        exposure_rates = ctx.feature_exposure_by_community("layer2")
        flagged: list[FlaggedItem] = []

        for comm_id, rate in exposure_rates.items():
            if rate >= EXPOSURE_GAP_THRESHOLD:
                continue
            members = ctx.community_members("layer2", comm_id)
            if len(members) < 5:
                continue
            flagged.append(
                FlaggedItem(
                    node_id=f"community_{comm_id}",
                    node_type="cluster",
                    score=1.0 - rate,
                    label=f"Community {comm_id}",
                    metrics={"exposure_rate": rate, "member_count": float(len(members))},
                    explanation=(
                        f"Community {comm_id} ({len(members)} users) has only {rate:.0%} feature exposure. "
                        "Low performance here may reflect lack of reach, not product fit."
                    ),
                    recommended_action="Prioritize targeted rollout or awareness campaign to this cluster before evaluating engagement metrics.",
                    extra={"community_id": comm_id, "member_ids": members[:10]},
                )
            )

        flagged.sort(key=lambda x: x.score, reverse=True)

        if not flagged:
            return UseCaseResult(
                use_case_id=self.use_case_id,
                title=self.title,
                flagged=[],
                empty_message="No clusters with significant feature discovery gaps detected.",
                supports_toggle=self.supports_toggle,
                required_layers=self.required_layers,
            )

        return UseCaseResult(
            use_case_id=self.use_case_id,
            title=self.title,
            flagged=flagged[:50],
            supports_toggle=self.supports_toggle,
            required_layers=self.required_layers,
        )

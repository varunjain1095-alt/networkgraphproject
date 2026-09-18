"""Use case #8 — fraud / fake-account ring detection."""

from __future__ import annotations

from use_cases.base import BaseUseCase, FlaggedItem, UseCaseResult
from use_cases.context import UseCaseContext

DENSITY_THRESHOLD = 0.35
MIN_CLUSTER_SIZE = 8


class FraudDetectionUseCase(BaseUseCase):
    use_case_id = "fraud_detection"
    title = "Fraud / fake-account ring detection"
    supports_toggle = False
    required_layers = ["layer1"]

    def run(self, ctx: UseCaseContext, most_important: bool = True) -> UseCaseResult:
        flagged: list[FlaggedItem] = []
        for row in ctx.cluster_metrics("layer1"):
            density = float(row["density"] or 0)
            count = int(row["node_count"])
            reciprocity = float(row["reciprocity"] or 0) if row["reciprocity"] is not None else 0.0
            if count < MIN_CLUSTER_SIZE or density < DENSITY_THRESHOLD:
                continue
            score = density * (1.0 + reciprocity)
            comm_id = int(row["community_id"])
            flagged.append(
                FlaggedItem(
                    node_id=f"community_{comm_id}",
                    node_type="cluster",
                    score=score,
                    label=f"Suspicious cluster {comm_id}",
                    metrics={"density": density, "reciprocity": reciprocity, "node_count": float(count)},
                    explanation=(
                        f"Cluster {comm_id} shows unusually dense, reciprocal connections "
                        f"(density {density:.2f}, {count} users). "
                        "Pattern may indicate coordinated or inorganic behavior."
                    ),
                    recommended_action="Review accounts in this cluster for trust-and-safety investigation before taking action.",
                    extra={"community_id": comm_id},
                )
            )

        flagged.sort(key=lambda x: x.score, reverse=True)

        if not flagged:
            return UseCaseResult(
                use_case_id=self.use_case_id,
                title=self.title,
                flagged=[],
                empty_message="No suspicious high-density clusters detected.",
                supports_toggle=self.supports_toggle,
                required_layers=self.required_layers,
            )

        return UseCaseResult(
            use_case_id=self.use_case_id,
            title=self.title,
            flagged=flagged[:30],
            supports_toggle=self.supports_toggle,
            required_layers=self.required_layers,
        )

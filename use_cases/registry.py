"""Registry of all use case modules."""

from __future__ import annotations

from use_cases.ab_contamination import ABContaminationUseCase
from use_cases.base import BaseUseCase, UseCaseResult
from use_cases.champion_churn import ChampionChurnUseCase
from use_cases.context import UseCaseContext
from use_cases.discovery_gap import DiscoveryGapUseCase
from use_cases.fraud_detection import FraudDetectionUseCase
from use_cases.onboarding_flow import OnboardingFlowUseCase
from use_cases.research_priority import ResearchPriorityUseCase
from use_cases.rollout_sequencing import RolloutSequencingUseCase
from use_cases.support_escalation import SupportEscalationUseCase

ALL_USE_CASES: list[BaseUseCase] = [
    OnboardingFlowUseCase(),
    DiscoveryGapUseCase(),
    FraudDetectionUseCase(),
    RolloutSequencingUseCase(),
    SupportEscalationUseCase(),
    ABContaminationUseCase(),
    ChampionChurnUseCase(),
    ResearchPriorityUseCase(),
]


def run_all(ctx: UseCaseContext | None = None, most_important: bool = True) -> dict[str, UseCaseResult]:
    own_ctx = ctx is None
    ctx = ctx or UseCaseContext()
    try:
        return {uc.use_case_id: uc.run(ctx, most_important=most_important) for uc in ALL_USE_CASES}
    finally:
        if own_ctx:
            ctx.close()


def get_use_case(use_case_id: str) -> BaseUseCase:
    for uc in ALL_USE_CASES:
        if uc.use_case_id == use_case_id:
            return uc
    raise KeyError(f"Unknown use case: {use_case_id}")

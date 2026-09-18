"""Scale targets for synthetic data generation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScaleConfig:
    n_users: int
    n_items: int
    n_sources: int
    n_orgs: int
    n_taste_clusters: int
    min_relationship_edges: int
    max_relationship_edges: int
    min_interactions: int
    max_interactions: int
    min_sessions: int
    max_sessions: int
    referral_rate: float
    active_user_fraction: float


SCALES: dict[str, ScaleConfig] = {
    "dev": ScaleConfig(
        n_users=500,
        n_items=100,
        n_sources=50,
        n_orgs=20,
        n_taste_clusters=10,
        min_relationship_edges=4_000,
        max_relationship_edges=10_000,
        min_interactions=8_000,
        max_interactions=20_000,
        min_sessions=10_000,
        max_sessions=25_000,
        referral_rate=0.12,
        active_user_fraction=0.85,
    ),
    "medium": ScaleConfig(
        n_users=2_500,
        n_items=350,
        n_sources=125,
        n_orgs=40,
        n_taste_clusters=15,
        min_relationship_edges=20_000,
        max_relationship_edges=50_000,
        min_interactions=40_000,
        max_interactions=100_000,
        min_sessions=50_000,
        max_sessions=125_000,
        referral_rate=0.14,
        active_user_fraction=0.87,
    ),
    "demo": ScaleConfig(
        n_users=10_000,
        n_items=1_000,
        n_sources=300,
        n_orgs=100,
        n_taste_clusters=20,
        min_relationship_edges=80_000,
        max_relationship_edges=200_000,
        min_interactions=150_000,
        max_interactions=400_000,
        min_sessions=200_000,
        max_sessions=500_000,
        referral_rate=0.15,
        active_user_fraction=0.88,
    ),
}


def get_scale(mode: str) -> ScaleConfig:
    key = mode.lower().strip()
    if key not in SCALES:
        raise ValueError(f"Unknown SCALE_MODE '{mode}'. Use: {', '.join(SCALES)}")
    return SCALES[key]

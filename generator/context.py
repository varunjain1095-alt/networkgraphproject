"""Shared generation context passed between generator modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np

from generator.scale import ScaleConfig


@dataclass
class GenerationContext:
    rng: np.random.Generator
    scale: ScaleConfig
    seed: int
    scale_mode: str
    config_hash: str

    org_ids: list[str] = field(default_factory=list)
    user_ids: list[str] = field(default_factory=list)
    item_ids: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)

    user_org: dict[str, str] = field(default_factory=dict)
    user_join: dict[str, date] = field(default_factory=dict)
    user_last_active: dict[str, date] = field(default_factory=dict)
    user_propensity: dict[str, float] = field(default_factory=dict)
    user_taste: dict[str, int] = field(default_factory=dict)
    user_active: dict[str, bool] = field(default_factory=dict)

    item_popularity: dict[str, float] = field(default_factory=dict)
    item_taste: dict[str, int] = field(default_factory=dict)
    item_release: dict[str, date] = field(default_factory=dict)

    source_specialization: dict[str, int] = field(default_factory=dict)

    adjacency: dict[str, set[str]] = field(default_factory=dict)
    relationship_pairs: set[tuple[str, str, str]] = field(default_factory=set)

    stats: dict[str, int | float] = field(default_factory=dict)

    def add_edge(self, user_a: str, user_b: str, rel_type: str) -> None:
        if rel_type in ("friend", "collaborate"):
            a, b = sorted((user_a, user_b))
        else:
            a, b = user_a, user_b
        key = (a, b, rel_type)
        if key in self.relationship_pairs:
            return
        self.relationship_pairs.add(key)
        self.adjacency.setdefault(user_a, set()).add(user_b)
        if rel_type in ("friend", "collaborate", "member_of"):
            self.adjacency.setdefault(user_b, set()).add(user_a)

    def neighbors(self, user_id: str) -> set[str]:
        return self.adjacency.get(user_id, set())

"""Shared use case interface and result types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FlaggedItem:
    node_id: str
    node_type: str = "user"
    score: float = 0.0
    rank: int = 0
    label: str = ""
    metrics: dict[str, float] = field(default_factory=dict)
    explanation: str = ""
    recommended_action: str = ""
    subgraph_center: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class UseCaseResult:
    use_case_id: str
    title: str
    flagged: list[FlaggedItem]
    empty_message: str | None = None
    supports_toggle: bool = False
    required_layers: list[str] = field(default_factory=list)
    metric_values: dict[str, Any] = field(default_factory=dict)

    @property
    def has_results(self) -> bool:
        return len(self.flagged) > 0

    def sorted(self, most_important: bool = True) -> list[FlaggedItem]:
        items = sorted(self.flagged, key=lambda x: x.score, reverse=most_important)
        for i, item in enumerate(items, start=1):
            item.rank = i
        return items


class BaseUseCase(ABC):
    use_case_id: str
    title: str
    supports_toggle: bool = False
    required_layers: list[str] = []

    @abstractmethod
    def run(self, ctx: "UseCaseContext", most_important: bool = True) -> UseCaseResult:
        raise NotImplementedError

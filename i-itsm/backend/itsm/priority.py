"""Priority calculation (Strategy pattern).

score = impact (1-4) x urgency (1-4) x business criticality (1-5), scaled up when
many people are affected. Bands: >=48 P1, >=24 P2, >=8 P3, otherwise P4.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .models import IncidentPriority, SystemConfiguration

P1_THRESHOLD, P2_THRESHOLD, P3_THRESHOLD = 48, 24, 8


@dataclass(frozen=True)
class PriorityResult:
    score: float
    priority: str
    rationale: tuple[str, ...]


def _band(score: float) -> str:
    if score >= P1_THRESHOLD:
        return IncidentPriority.P1
    if score >= P2_THRESHOLD:
        return IncidentPriority.P2
    if score >= P3_THRESHOLD:
        return IncidentPriority.P3
    return IncidentPriority.P4


def _user_multiplier(affected_users: int) -> float:
    if affected_users >= 100:
        return 1.5
    if affected_users >= 20:
        return 1.25
    return 1.0


class PriorityStrategy(ABC):
    key: str
    label: str
    description: str

    @abstractmethod
    def calculate(self, impact: int, urgency: int, criticality: int, affected_users: int) -> PriorityResult:
        """Return the score, band and a human-readable explanation."""


class WeightedScoringPriorityStrategy(PriorityStrategy):
    key = "weighted"
    label = "Weighted score"
    description = "Impact x urgency x criticality, scaled by the number of people affected."

    def calculate(self, impact, urgency, criticality, affected_users):
        multiplier = _user_multiplier(affected_users)
        score = round(impact * urgency * criticality * multiplier, 2)
        rationale = [f"Impact {impact} x urgency {urgency} x criticality {criticality} = {impact * urgency * criticality}"]
        if multiplier > 1:
            rationale.append(f"{affected_users} people affected, score x{multiplier}")
        return PriorityResult(score, _band(score), tuple(rationale))


class RuleBasedPriorityStrategy(PriorityStrategy):
    key = "rule_based"
    label = "Rule based"
    description = "Weighted score, but significant impact on a top-criticality service is always P1."

    def __init__(self):
        self._weighted = WeightedScoringPriorityStrategy()

    def calculate(self, impact, urgency, criticality, affected_users):
        result = self._weighted.calculate(impact, urgency, criticality, affected_users)
        if impact >= 3 and criticality >= 5 and result.priority != IncidentPriority.P1:
            return PriorityResult(max(result.score, P1_THRESHOLD), IncidentPriority.P1,
                                  result.rationale + ("Rule: impact 3+ on a criticality-5 service is always P1",))
        return result


PRIORITY_STRATEGIES: dict[str, PriorityStrategy] = {
    strategy.key: strategy for strategy in (WeightedScoringPriorityStrategy(), RuleBasedPriorityStrategy())
}


def get_priority_strategy(key: str | None = None) -> PriorityStrategy:
    key = key or SystemConfiguration.current().priority_strategy
    return PRIORITY_STRATEGIES.get(key, PRIORITY_STRATEGIES["weighted"])


def calculate_incident_priority(impact: int, urgency: int, service, affected_users: int = 1,
                                strategy: PriorityStrategy | None = None) -> PriorityResult:
    """Priority for an incident, using the service's dependency-aware criticality."""
    from .insights import effective_criticality

    criticality, reason = effective_criticality(service) if service else (1, None)
    result = (strategy or get_priority_strategy()).calculate(impact, urgency, criticality, affected_users)
    if reason:
        result = PriorityResult(result.score, result.priority, result.rationale + (reason,))
    return result

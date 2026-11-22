"""Strategy pattern for priority calculation.
Weighted score = Impact(1-4) x Urgency(1-4) x Business criticality(1-5)  -> 1..80, scaled up for many affected users.
Bands: >=48 P1 | >=24 P2 | >=8 P3 | else P4."""
from abc import ABC, abstractmethod

BANDS = [(48, "P1"), (24, "P2"), (8, "P3")]


def band(score):
    for threshold, p in BANDS:
        if score >= threshold:
            return p
    return "P4"


class PriorityStrategy(ABC):
    @abstractmethod
    def calculate(self, impact, urgency, criticality, affected_users): ...


class WeightedScorePriority(PriorityStrategy):
    def calculate(self, impact, urgency, criticality, affected_users):
        score = impact * urgency * criticality
        if affected_users >= 100:
            score *= 1.5
        elif affected_users >= 20:
            score *= 1.25
        return round(score, 2), band(score)


class RuleBasedPriority(PriorityStrategy):
    """Weighted score, but a high-impact incident on a mission-critical service is always P1."""
    def calculate(self, impact, urgency, criticality, affected_users):
        score, p = WeightedScorePriority().calculate(impact, urgency, criticality, affected_users)
        if criticality >= 5 and impact >= 3:
            p = "P1"
        return score, p


STRATEGIES = {"WEIGHTED": WeightedScorePriority, "RULE": RuleBasedPriority}


def get_priority_strategy():
    from .models import SystemSetting
    return STRATEGIES[SystemSetting.load().priority_strategy]()

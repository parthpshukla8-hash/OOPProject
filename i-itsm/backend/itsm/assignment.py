"""Technician assignment (Strategy pattern). The administrator picks the strategy at runtime."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from django.db.models import Count

from .exceptions import TechnicianUnavailable, TechnicianWorkloadExceeded
from .intelligence import TechnicianAffinity
from .models import Incident, SystemConfiguration, User, WORKING_STATUSES


@dataclass(frozen=True)
class Recommendation:
    technician: User
    score: float
    reasons: tuple[str, ...]


def current_loads() -> dict[int, int]:
    rows = (Incident.objects.filter(status__in=WORKING_STATUSES, assignee__isnull=False)
            .values("assignee").annotate(n=Count("id")))
    return {row["assignee"]: row["n"] for row in rows}


def _has_skill(technician: User, incident: Incident) -> bool:
    return bool(incident.category_id) and technician.skills.filter(pk=incident.category_id).exists()


class AssignmentStrategy(ABC):
    key: str
    label: str
    description: str

    @abstractmethod
    def rank(self, incident: Incident, candidates: list[User], loads: dict[int, int]) -> list[Recommendation]:
        """Best candidate first."""

    def record_assignment(self, technician: User) -> None:
        """Hook for strategies that keep state between assignments."""


class SkillBasedAssignmentStrategy(AssignmentStrategy):
    key, label = "skill", "Skill based"
    description = "Technicians skilled in the incident's category first; ties go to the lighter workload."

    def rank(self, incident, candidates, loads):
        ranked = []
        for t in candidates:
            skilled = _has_skill(t, incident)
            reasons = ("Skilled in this category",) if skilled else ("No matching skill",)
            ranked.append(Recommendation(t, 100.0 if skilled else 0.0, reasons))
        return sorted(ranked, key=lambda r: (-r.score, loads.get(r.technician.pk, 0), r.technician.pk))


class LoadBasedAssignmentStrategy(AssignmentStrategy):
    key, label = "load", "Load based"
    description = "The technician with the most free capacity."

    def rank(self, incident, candidates, loads):
        ranked = []
        for t in candidates:
            used = loads.get(t.pk, 0)
            ranked.append(Recommendation(t, round(100 * (1 - used / max(t.max_active_incidents, 1)), 1),
                                         (f"{used} of {t.max_active_incidents} slots in use",)))
        return sorted(ranked, key=lambda r: (-r.score, r.technician.pk))


class RoundRobinAssignmentStrategy(AssignmentStrategy):
    key, label = "round_robin", "Round robin"
    description = "Take turns, regardless of skill or load."

    def rank(self, incident, candidates, loads):
        last_id = SystemConfiguration.current().round_robin_cursor
        ordered = sorted(candidates, key=lambda t: t.pk)
        after = [t for t in ordered if t.pk > last_id]
        rotated = after + [t for t in ordered if t.pk <= last_id]
        return [Recommendation(t, float(len(rotated) - i), ("Next in turn",) if i == 0 else ())
                for i, t in enumerate(rotated)]

    def record_assignment(self, technician):
        configuration = SystemConfiguration.current()
        configuration.round_robin_cursor = technician.pk
        configuration.save(update_fields=["round_robin_cursor"])


class SmartAssignmentStrategy(AssignmentStrategy):
    """Skill 40 + free capacity 30 + experience 20 + similarity to past work 10 (cosine)."""
    key, label = "smart", "Smart match"
    description = "Skill, free capacity, experience and how similar their past incidents are (cosine similarity)."

    def rank(self, incident, candidates, loads):
        affinities = TechnicianAffinity(candidates).scores_for(incident.search_text)
        ranked = []
        for t in candidates:
            used = loads.get(t.pk, 0)
            skill = 40.0 if _has_skill(t, incident) else 0.0
            capacity = 30.0 * max(0.0, 1 - used / max(t.max_active_incidents, 1))
            experience = 20.0 * min(t.experience_years, 10) / 10
            similarity = affinities.get(t.pk, 0.0)
            history = 10.0 * min(similarity / 0.5, 1.0)
            reasons = []
            if skill:
                reasons.append("Skilled in this category")
            reasons.append(f"{used} of {t.max_active_incidents} slots in use")
            if t.experience_years:
                reasons.append(f"{t.experience_years} years of experience")
            if similarity >= 0.1:
                reasons.append(f"Resolved similar incidents (similarity {similarity:.2f})")
            ranked.append(Recommendation(t, round(skill + capacity + experience + history, 1), tuple(reasons)))
        return sorted(ranked, key=lambda r: (-r.score, r.technician.pk))


ASSIGNMENT_STRATEGIES: dict[str, AssignmentStrategy] = {
    s.key: s for s in (SkillBasedAssignmentStrategy(), LoadBasedAssignmentStrategy(),
                       RoundRobinAssignmentStrategy(), SmartAssignmentStrategy())
}


def get_assignment_strategy(key: str | None = None) -> AssignmentStrategy:
    key = key or SystemConfiguration.current().assignment_strategy
    return ASSIGNMENT_STRATEGIES.get(key, ASSIGNMENT_STRATEGIES["smart"])


def eligible_technicians(loads: dict[int, int]) -> list[User]:
    """Active, available technicians with spare capacity. Raises if there are none."""
    technicians = list(User.objects.filter(role=User.Role.TECHNICIAN, is_active=True, is_available=True))
    if not technicians:
        raise TechnicianUnavailable()
    with_capacity = [t for t in technicians if loads.get(t.pk, 0) < t.max_active_incidents]
    if not with_capacity:
        raise TechnicianWorkloadExceeded("Every available technician is at their workload limit.")
    return with_capacity


def recommend_technicians(incident: Incident, strategy: AssignmentStrategy | None = None,
                          limit: int = 3) -> list[Recommendation]:
    loads = current_loads()
    return (strategy or get_assignment_strategy()).rank(incident, eligible_technicians(loads), loads)[:limit]


def pick_technician(incident: Incident, strategy: AssignmentStrategy | None = None) -> Recommendation:
    strategy = strategy or get_assignment_strategy()
    best = recommend_technicians(incident, strategy, limit=1)[0]
    strategy.record_assignment(best.technician)
    return best

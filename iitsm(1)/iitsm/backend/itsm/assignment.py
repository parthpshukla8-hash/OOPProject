"""Strategy pattern for technician assignment. Switchable at runtime via SystemSetting."""
from abc import ABC, abstractmethod

from django.utils import timezone

from .exceptions import TechnicianUnavailable, WorkloadExceeded
from .models import DONE_STATUSES, Incident, technician_pool


def eligible_technicians():
    pool = list(technician_pool())
    available = [t for t in pool if t.is_available]
    if not available:
        raise TechnicianUnavailable("No technician is currently available.")
    free = [t for t in available if t.load_count < t.max_load]
    if not free:
        raise WorkloadExceeded("All available technicians have reached their maximum workload.")
    return free


def _skill_ids(tech):
    return {s.id for s in tech.skills.all()}


class AssignmentStrategy(ABC):
    @abstractmethod
    def pick(self, incident, candidates): ...


class SkillBased(AssignmentStrategy):
    def pick(self, incident, candidates):
        skilled = [t for t in candidates if incident.category_id in _skill_ids(t)] or candidates
        return min(skilled, key=lambda t: (t.load_count, -t.experience_years))


class LoadBased(AssignmentStrategy):
    def pick(self, incident, candidates):
        return min(candidates, key=lambda t: (t.load_count / max(t.max_load, 1), t.id))


class RoundRobin(AssignmentStrategy):
    def pick(self, incident, candidates):
        now = timezone.now()
        return min(candidates, key=lambda t: (t.last_assigned_at is not None, t.last_assigned_at or now, t.id))


class SmartRecommendation(AssignmentStrategy):
    """Weighted: skill match 40, free capacity 30, experience 20, history on the same service 10."""
    def score(self, incident, t):
        skill = 40 if incident.category_id in _skill_ids(t) else 0
        capacity = 30 * (1 - t.load_count / max(t.max_load, 1))
        exp = 20 * min(t.experience_years / 10, 1)
        done = Incident.objects.filter(assignee=t, service=incident.service, status__in=DONE_STATUSES).count()
        history = 10 * min(done / 5, 1)
        return round(skill + capacity + exp + history, 1), {
            "skill": skill, "capacity": round(capacity, 1), "experience": round(exp, 1), "history": round(history, 1)}

    def rank(self, incident, candidates):
        rows = []
        for t in candidates:
            s, parts = self.score(incident, t)
            rows.append({"technician": t, "score": s, "breakdown": parts})
        return sorted(rows, key=lambda r: -r["score"])

    def pick(self, incident, candidates):
        return self.rank(incident, candidates)[0]["technician"]


STRATEGIES = {"SKILL": SkillBased, "LOAD": LoadBased, "ROUND_ROBIN": RoundRobin, "SMART": SmartRecommendation}


def get_assignment_strategy():
    from .models import SystemSetting
    return STRATEGIES[SystemSetting.load().assignment_strategy]()

"""Service dependency graph, root-cause analysis, dependency-aware criticality, SLA prediction."""
from __future__ import annotations

import math
from collections import defaultdict, deque
from datetime import datetime

from django.db.models import F
from django.utils import timezone

from .exceptions import DependencyCycle, InvalidUserInput
from .models import (FINISHED_STATUSES, Incident, IncidentPriority, OPEN_STATUSES, Service,
                     ServiceDependency)
from .sla import find_sla_policy


def _edges() -> list[tuple[int, int]]:
    return list(ServiceDependency.objects.values_list("service_id", "depends_on_id"))


def _walk(start_id: int, adjacency: dict[int, list[int]]) -> dict[int, int]:
    """Breadth-first walk. Returns {service_id: distance} (start excluded)."""
    distances, queue = {}, deque([(start_id, 0)])
    while queue:
        current, depth = queue.popleft()
        for neighbour in adjacency.get(current, []):
            if neighbour != start_id and neighbour not in distances:
                distances[neighbour] = depth + 1
                queue.append((neighbour, depth + 1))
    return distances


def _adjacency(reverse: bool = False) -> dict[int, list[int]]:
    graph = defaultdict(list)
    for service_id, depends_on_id in _edges():
        if reverse:
            graph[depends_on_id].append(service_id)
        else:
            graph[service_id].append(depends_on_id)
    return graph


def upstream_distances(service_id: int) -> dict[int, int]:
    """Services this one relies on, with distance."""
    return _walk(service_id, _adjacency())


def downstream_distances(service_id: int) -> dict[int, int]:
    """Services that rely on this one, with distance (its blast radius)."""
    return _walk(service_id, _adjacency(reverse=True))


def add_dependency(service: Service, depends_on: Service) -> ServiceDependency:
    if service.pk == depends_on.pk:
        raise InvalidUserInput("A service cannot depend on itself.")
    if service.pk in upstream_distances(depends_on.pk):
        raise DependencyCycle(f"{depends_on.name} already relies on {service.name}.")
    dependency, _ = ServiceDependency.objects.get_or_create(service=service, depends_on=depends_on)
    return dependency


def effective_criticality(service: Service) -> tuple[int, str | None]:
    """A service is at least as critical as the most critical service relying on it."""
    downstream_ids = downstream_distances(service.pk)
    if not downstream_ids:
        return service.business_criticality, None
    top = Service.objects.filter(pk__in=downstream_ids).order_by("-business_criticality").first()
    if top and top.business_criticality > service.business_criticality:
        return top.business_criticality, (
            f"Criticality raised from {service.business_criticality} to {top.business_criticality} "
            f"because {top.name} relies on {service.name}")
    return service.business_criticality, None


def find_probable_root_cause(incident: Incident) -> Incident | None:
    """Deepest upstream service that already has an open incident, if any."""
    if not incident.service_id:
        return None
    upstream = upstream_distances(incident.service_id)
    if not upstream:
        return None
    candidates = (Incident.objects.filter(service_id__in=upstream, status__in=OPEN_STATUSES)
                  .exclude(pk=incident.pk).select_related("service"))
    ranked = sorted(candidates, key=lambda i: (-upstream[i.service_id], i.priority, i.created_at))
    return ranked[0] if ranked else None


def predict_sla_breach(incident: Incident, now: datetime | None = None) -> dict:
    """Probability that an open incident misses its resolution target.

    expected effort (history for category+priority, else half the SLA)
      -> remaining effort -> inflated by the technician's queue (+15% per other active incident)
      -> compared with the time left, through a logistic curve.
    """
    now = now or timezone.now()
    if not incident.resolution_due_at or not incident.is_open:
        return {"probability": 0.0, "expected_minutes": None, "minutes_left": None}
    history = Incident.objects.filter(status__in=FINISHED_STATUSES, priority=incident.priority,
                                      category_id=incident.category_id, resolved_at__isnull=False
                                      ).exclude(pk=incident.pk)
    durations = [(i.resolved_at - i.created_at).total_seconds() / 60 for i in history[:100]]
    if len(durations) >= 3:
        expected = sum(durations) / len(durations)
    else:
        expected = 0.5 * find_sla_policy(incident.priority, incident.service).resolution_minutes
    elapsed = (now - incident.created_at).total_seconds() / 60
    remaining_work = max(expected - elapsed, expected * 0.1)
    queue = max(incident.assignee.active_incident_count - 1, 0) if incident.assignee_id else 3
    inflated = remaining_work * (1 + 0.15 * queue)
    minutes_left = (incident.resolution_due_at - now).total_seconds() / 60
    if minutes_left <= 0:
        probability = 1.0
    else:
        probability = 1 / (1 + math.exp(-6 * (inflated / minutes_left - 1)))
    return {"probability": round(probability, 2), "expected_minutes": round(expected, 1),
            "minutes_left": round(minutes_left, 1)}


def service_health() -> dict:
    """Nodes and edges for the service map, with open-incident counts per service."""
    open_by_service = defaultdict(list)
    for incident in Incident.objects.filter(status__in=OPEN_STATUSES, service__isnull=False):
        open_by_service[incident.service_id].append(incident.priority)
    nodes = []
    for service in Service.objects.filter(is_active=True):
        priorities = open_by_service.get(service.pk, [])
        worst = min(priorities) if priorities else None
        nodes.append({
            "id": service.pk, "name": service.name, "business_criticality": service.business_criticality,
            "open_incidents": len(priorities), "worst_priority": worst,
            "health": "down" if worst == IncidentPriority.P1 else "degraded" if priorities else "healthy",
            "relies_on": sorted(upstream_distances(service.pk)),
            "affects": sorted(downstream_distances(service.pk)),
        })
    return {"nodes": nodes, "edges": [{"service": s, "depends_on": d} for s, d in _edges()]}

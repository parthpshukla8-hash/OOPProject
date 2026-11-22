"""Innovation layer: service dependency graph, root-cause analysis, dependency-aware criticality,
predictive SLA breach scoring."""
import math

from django.utils import timezone

from .models import DONE_STATUSES, Incident, ServiceDependency


def walk(service, up=True):
    """Breadth-first traversal of the dependency graph (cycle-safe).
    up=True  -> services `service` depends on (its infrastructure)
    up=False -> services that depend on `service` (its blast radius)
    Returns {service_pk: (Service, depth)}."""
    seen, frontier, depth = {}, [service], 0
    while frontier:
        depth += 1
        nxt = []
        for s in frontier:
            qs = (ServiceDependency.objects.filter(service=s).select_related("depends_on") if up
                  else ServiceDependency.objects.filter(depends_on=s).select_related("service"))
            for edge in qs:
                t = edge.depends_on if up else edge.service
                if t.pk != service.pk and t.pk not in seen:
                    seen[t.pk] = (t, depth)
                    nxt.append(t)
        frontier = nxt
    return seen


def effective_criticality(service):
    """Dependency-aware: a service is at least as critical as the most critical service relying on it."""
    return max([service.business_criticality] + [s.business_criticality for s, _ in walk(service, up=False).values()])


def blast_radius(service):
    return sorted(({"name": s.name, "criticality": s.business_criticality, "depth": d}
                   for s, d in walk(service, up=False).values()), key=lambda r: (r["depth"], -r["criticality"]))


def root_cause(incident):
    """If upstream services have open incidents, the deepest one is the probable root cause."""
    ups = walk(incident.service, up=True)
    if not ups:
        return None
    by_service = {}
    for i in Incident.objects.filter(service_id__in=ups.keys()).exclude(status__in=DONE_STATUSES).exclude(pk=incident.pk):
        by_service.setdefault(i.service_id, []).append(i.number)
    if not by_service:
        return None
    sid = max(by_service, key=lambda k: ups[k][1])
    svc, depth = ups[sid]
    return {"service": svc.name, "service_id": svc.pk, "incidents": by_service[sid], "depth": depth,
            "also_affected_upstream": [ups[k][0].name for k in by_service if k != sid]}


# ---------------------------------------------------------------- predictive SLA
def history():
    """Observed resolution minutes keyed by (category, priority) and by priority (ignores instant/seed data)."""
    h = {}
    for cat, pr, created, resolved in Incident.objects.filter(resolved_at__isnull=False).values_list(
            "category_id", "priority", "created_at", "resolved_at"):
        minutes = (resolved - created).total_seconds() / 60
        if minutes >= 1:
            h.setdefault((cat, pr), []).append(minutes)
            h.setdefault(pr, []).append(minutes)
    return h


def predict(incident, hist=None, now=None):
    """Estimate total resolution time and the probability of breaching the resolution SLA.
    expected   = mean historical time for same category+priority (fallback: priority, then 50% of the SLA window)
    remaining  = max(expected - elapsed, 25% of expected)       (an open incident is never 'almost done' for free)
    queue load = +15% per active incident of the assigned technician (3 if unassigned)
    probability = logistic((predicted_total - window) / (25% of window))"""
    if incident.status in DONE_STATUSES or not incident.resolution_due:
        return None
    hist = history() if hist is None else hist
    now = now or timezone.now()
    window = max((incident.resolution_due - incident.created_at).total_seconds() / 60, 1)
    elapsed = max((now - incident.created_at).total_seconds() / 60, 0)
    samples = hist.get((incident.category_id, incident.priority)) or hist.get(incident.priority) or []
    expected = max(sum(samples) / len(samples), 0.1 * window) if samples else 0.5 * window
    load = incident.assignee.active_load if incident.assignee else 3
    total = elapsed + max(expected - elapsed, 0.25 * expected) * (1 + 0.15 * load)
    z = max(min((total - window) / (0.25 * window), 30), -30)
    p = 1 / (1 + math.exp(-z))
    return {"predicted_minutes": round(total), "window_minutes": round(window), "probability": round(p, 2),
            "level": "HIGH" if p >= 0.6 else "MEDIUM" if p >= 0.35 else "LOW", "samples": len(samples)}

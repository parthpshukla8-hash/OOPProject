"""Reporting and the admin 'situation' view."""
from __future__ import annotations

from collections import Counter
from datetime import timedelta

from django.db.models import Avg, Count, F, Q
from django.utils import timezone

from .insights import predict_sla_breach
from .intelligence import correlate_open_incidents
from .models import FINISHED_STATUSES, Incident, IncidentPriority, IncidentStatus, OPEN_STATUSES, SystemConfiguration, User
from .sla import PRE_ACKNOWLEDGEMENT_STATUSES, SlaMonitor, check_sla_compliance, SlaStatus

MONITOR_INTERVAL_SECONDS = 30


def run_sla_monitor_if_due(force: bool = False):
    configuration = SystemConfiguration.current()
    now = timezone.now()
    last = configuration.last_sla_check_at
    if force or last is None or (now - last).total_seconds() >= MONITOR_INTERVAL_SECONDS:
        configuration.last_sla_check_at = now
        configuration.save(update_fields=["last_sla_check_at"])
        return SlaMonitor().run(now)
    return None


def _minutes(delta) -> float:
    return round(delta.total_seconds() / 60, 1)


def predicted_breaches(threshold: float = 0.5, limit: int = 8) -> list[dict]:
    rows = []
    for incident in Incident.objects.filter(status__in=OPEN_STATUSES).select_related("assignee", "service"):
        if incident.resolution_breached:
            continue
        prediction = predict_sla_breach(incident)
        if prediction["probability"] >= threshold:
            rows.append({"incident_id": incident.pk, "code": incident.code, "title": incident.title,
                         "priority": incident.priority, **prediction})
    return sorted(rows, key=lambda r: -r["probability"])[:limit]


def overview() -> dict:
    incidents = Incident.objects.all()
    finished = incidents.filter(status__in=FINISHED_STATUSES)
    durations = [(i.resolved_at - i.created_at) for i in finished.filter(resolved_at__isnull=False)]
    by_priority = {p: 0 for p in IncidentPriority.values}
    by_priority.update({r["priority"]: r["n"] for r in incidents.values("priority").annotate(n=Count("id"))})
    average = {}
    for priority in IncidentPriority.values:
        deltas = [i.resolved_at - i.created_at for i in finished.filter(priority=priority, resolved_at__isnull=False)]
        average[priority] = _minutes(sum(deltas, timedelta()) / len(deltas)) if deltas else None
    feedback = finished.filter(feedback_rating__isnull=False).aggregate(avg=Avg("feedback_rating"), n=Count("id"))
    today = timezone.localdate()
    daily = Counter(timezone.localtime(i.created_at).date() for i in
                    incidents.filter(created_at__gte=timezone.now() - timedelta(days=14)))
    return {
        "total": incidents.count(),
        "open": incidents.filter(status__in=OPEN_STATUSES).count(),
        "critical_open": incidents.filter(status__in=OPEN_STATUSES, priority=IncidentPriority.P1).count(),
        "resolved": finished.count(),
        "sla_violations": incidents.filter(Q(response_breached=True) | Q(resolution_breached=True)).count(),
        "average_resolution_minutes": _minutes(sum(durations, timedelta()) / len(durations)) if durations else None,
        "average_resolution_by_priority": average,
        "by_priority": by_priority,
        "by_status": {r["status"]: r["n"] for r in incidents.values("status").annotate(n=Count("id"))},
        "by_service": list(incidents.values(name=F("service__name"))
                           .annotate(count=Count("id")).order_by("-count")),
        "by_category": list(incidents.values(name=F("category__name"))
                            .annotate(count=Count("id")).order_by("-count")),
        "feedback": {"average": round(feedback["avg"], 2) if feedback["avg"] else None, "count": feedback["n"]},
        "daily_volume": [{"date": (today - timedelta(days=d)).isoformat(),
                          "count": daily.get(today - timedelta(days=d), 0)} for d in range(13, -1, -1)],
    }


def technician_workload() -> list[dict]:
    rows = []
    for technician in User.objects.filter(role=User.Role.TECHNICIAN, is_active=True):
        resolved = technician.assigned_incidents.filter(status__in=FINISHED_STATUSES)
        rows.append({
            "id": technician.pk, "name": technician.display_name, "username": technician.username,
            "active": technician.active_incident_count, "capacity": technician.max_active_incidents,
            "resolved": resolved.count(), "is_available": technician.is_available,
            "skills": [s.name for s in technician.skills.all()],
        })
    return sorted(rows, key=lambda r: -r["active"])


def full_report() -> dict:
    return {**overview(), "technician_workload": technician_workload(),
            "correlations": correlate_open_incidents(), "predicted_breaches": predicted_breaches()}


def situation() -> dict:
    """What needs a human right now, ordered by urgency. Drives the administrator home page."""
    run_sla_monitor_if_due()
    now = timezone.now()
    attention = []
    for incident in Incident.objects.filter(status__in=OPEN_STATUSES).select_related("assignee", "service"):
        snapshot = check_sla_compliance(incident, now)
        reasons = []
        if incident.assignee_id is None:
            reasons.append("Nobody is assigned")
        if incident.escalation_level > 1:
            reasons.append(f"Escalated to level {incident.escalation_level}")
        if incident.status in PRE_ACKNOWLEDGEMENT_STATUSES and incident.response_breached:
            reasons.append("Not acknowledged in time")
        elif incident.resolution_breached:
            reasons.append("Resolution deadline missed")
        elif snapshot.status == SlaStatus.AT_RISK:
            reasons.append("Close to its deadline")
        if reasons:
            attention.append({"incident_id": incident.pk, "code": incident.code, "title": incident.title,
                              "priority": incident.priority, "reasons": reasons,
                              "assignee": incident.assignee.display_name if incident.assignee_id else None,
                              "minutes_to_resolution_due": snapshot.minutes_to_resolution_due})
    attention.sort(key=lambda r: (r["priority"], -len(r["reasons"])))
    return {"attention": attention, "predicted_breaches": predicted_breaches(),
            "correlations": correlate_open_incidents(), "overview": overview()}

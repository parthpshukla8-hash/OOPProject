"""SLA lookup, deadline calculation, risk detection, violation recording, automatic escalation."""
from datetime import timedelta

from django.utils import timezone

from .events import Event, bus
from .exceptions import MissingSLAConfiguration
from .models import DONE_STATUSES, Incident, SLAPolicy

ESCALATION_CHAIN = ["Technician", "Team Lead", "System Administrator", "IT Manager"]
WARN_RATIO = 0.8


def get_policy(service, priority):
    policy = (SLAPolicy.objects.filter(service=service, priority=priority).first()
              or SLAPolicy.objects.filter(service__isnull=True, priority=priority).first())
    if policy is None:
        raise MissingSLAConfiguration(f"No SLA policy configured for {service.name} / {priority}.")
    return policy


def apply_sla(incident, base_time):
    p = get_policy(incident.service, incident.priority)
    incident.response_due = base_time + timedelta(minutes=p.response_minutes)
    incident.resolution_due = base_time + timedelta(minutes=p.resolution_minutes)
    return p


def _ratio(start, due, now):
    total = (due - start).total_seconds()
    return (now - start).total_seconds() / total if total > 0 else 1


def risk(incident, now=None):
    """BREACHED / HIGH / MEDIUM / LOW  (SLA risk detection)."""
    now = now or timezone.now()
    if incident.status in DONE_STATUSES:
        return "BREACHED" if (incident.response_breached or incident.resolution_breached) else "LOW"
    if incident.response_breached or incident.resolution_breached:
        return "BREACHED"
    if not incident.resolution_due:
        return "LOW"
    if now > incident.resolution_due or (not incident.acknowledged_at and now > incident.response_due):
        return "BREACHED"
    r_res = _ratio(incident.created_at, incident.resolution_due, now)
    r_resp = 0 if incident.acknowledged_at else _ratio(incident.created_at, incident.response_due, now)
    worst = max(r_res, r_resp)
    if worst >= WARN_RATIO:
        return "HIGH"
    if worst >= 0.5 or (incident.assignee and incident.assignee.active_load >= incident.assignee.max_load):
        return "MEDIUM"
    return "LOW"


def sla_status(incident, now=None):
    r = risk(incident, now)
    if r == "BREACHED":
        return "BREACHED"
    if incident.status in DONE_STATUSES:
        return "MET"
    return "AT_RISK" if r == "HIGH" else "ON_TRACK"


def check_all(now=None):
    """Background SLA monitor: warnings, violation recording, escalation. Safe to call repeatedly."""
    now = now or timezone.now()
    out = {"warnings": 0, "breaches": 0, "escalations": 0}
    for inc in Incident.objects.exclude(status__in=DONE_STATUSES).select_related("assignee", "reporter", "service"):
        if inc.response_due and not inc.acknowledged_at and now > inc.response_due and not inc.response_breached:
            inc.response_breached = True
            inc.save(update_fields=["response_breached"])
            bus.publish(Event("SLA_BREACHED", inc, None, "Response SLA violated (not acknowledged in time)"))
            out["breaches"] += 1
        if inc.resolution_due and now > inc.resolution_due and not inc.resolution_breached:
            inc.resolution_breached = True
            inc.save(update_fields=["resolution_breached"])
            bus.publish(Event("SLA_BREACHED", inc, None, "Resolution SLA violated"))
            out["breaches"] += 1
        elif not inc.warning_sent and risk(inc, now) == "HIGH":
            inc.warning_sent = True
            inc.save(update_fields=["warning_sent"])
            bus.publish(Event("SLA_WARNING", inc, None, "SLA deadline approaching (>=80% of time elapsed)"))
            out["warnings"] += 1
        # automatic escalation of unacknowledged P1/P2 incidents
        if inc.priority in ("P1", "P2") and not inc.acknowledged_at and inc.response_due and now > inc.response_due:
            window = max((inc.response_due - inc.created_at).total_seconds(), 60)
            level = min(int((now - inc.response_due).total_seconds() // window) + 1, len(ESCALATION_CHAIN) - 1)
            if level > inc.escalation_level:
                inc.escalation_level = level
                inc.save(update_fields=["escalation_level"])
                bus.publish(Event("ESCALATED", inc, None, f"Escalated to {ESCALATION_CHAIN[level]} (unacknowledged {inc.priority})"))
                out["escalations"] += 1
    return out

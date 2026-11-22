"""SLA policy lookup, deadline calculation, compliance checks, monitoring and escalation."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from django.utils import timezone

from .events import DomainEvent, event_bus
from .exceptions import MissingSlaConfiguration
from .models import Incident, IncidentPriority, IncidentStatus, OPEN_STATUSES, SlaPolicy, User

WARNING_THRESHOLD = 0.8
ESCALATION_LEVELS = ("Technician", "Team lead", "System administrator", "IT manager")
PRE_ACKNOWLEDGEMENT_STATUSES = (IncidentStatus.NEW, IncidentStatus.CLASSIFIED, IncidentStatus.ASSIGNED)


class SlaStatus(str, Enum):
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    BREACHED = "breached"
    MET = "met"


def find_sla_policy(priority: str, service) -> SlaPolicy:
    """Service-specific policy first, then the organisation default for the priority."""
    if service is not None:
        policy = SlaPolicy.objects.filter(priority=priority, service=service).first()
        if policy:
            return policy
    policy = SlaPolicy.objects.filter(priority=priority, service__isnull=True).first()
    if policy is None:
        raise MissingSlaConfiguration(f"No SLA policy is configured for {priority} incidents.")
    return policy


def calculate_sla_deadline(start: datetime, minutes: int) -> datetime:
    return start + timedelta(minutes=minutes)


def apply_sla_deadlines(incident: Incident, start: datetime | None = None) -> SlaPolicy:
    policy = find_sla_policy(incident.priority, incident.service)
    start = start or incident.created_at or timezone.now()
    incident.response_due_at = calculate_sla_deadline(start, policy.response_minutes)
    incident.resolution_due_at = calculate_sla_deadline(start, policy.resolution_minutes)
    return policy


@dataclass(frozen=True)
class SlaSnapshot:
    status: SlaStatus
    response_progress: float
    resolution_progress: float
    minutes_to_resolution_due: float | None


def _progress(start: datetime, due: datetime | None, at: datetime) -> float:
    if not due or due <= start:
        return 0.0
    return max(0.0, (at - start).total_seconds() / (due - start).total_seconds())


def check_sla_compliance(incident: Incident, now: datetime | None = None) -> SlaSnapshot:
    now = now or timezone.now()
    response_end = incident.acknowledged_at or now
    resolution_end = incident.resolved_at or now
    response_progress = _progress(incident.created_at, incident.response_due_at, response_end)
    resolution_progress = _progress(incident.created_at, incident.resolution_due_at, resolution_end)
    breached = (incident.response_breached or incident.resolution_breached
                or (incident.acknowledged_at is None and incident.response_due_at and now > incident.response_due_at
                    and incident.status in PRE_ACKNOWLEDGEMENT_STATUSES)
                or (incident.is_open and incident.resolution_due_at and now > incident.resolution_due_at))
    if breached:
        status = SlaStatus.BREACHED
    elif not incident.is_open:
        status = SlaStatus.MET
    else:
        in_response_phase = incident.status in PRE_ACKNOWLEDGEMENT_STATUSES
        active_progress = response_progress if in_response_phase else resolution_progress
        status = SlaStatus.AT_RISK if max(active_progress, resolution_progress) >= WARNING_THRESHOLD \
            else SlaStatus.ON_TRACK
    minutes_left = None
    if incident.resolution_due_at and incident.is_open:
        minutes_left = round((incident.resolution_due_at - now).total_seconds() / 60, 1)
    return SlaSnapshot(status, round(response_progress, 3), round(resolution_progress, 3), minutes_left)


class EscalationChain:
    """Technician -> Team lead -> System administrator -> IT manager."""

    @staticmethod
    def recipient_for(level: int, incident: Incident) -> User | None:
        admins = User.objects.filter(role=User.Role.ADMINISTRATOR, is_active=True)
        if level <= 1:
            return incident.assignee
        if level == 2:
            lead = incident.assignee.team_lead if incident.assignee_id else None
            return lead or admins.filter(is_it_manager=False).first()
        if level == 3:
            return admins.filter(is_it_manager=False).first() or admins.first()
        return admins.filter(is_it_manager=True).first() or admins.first()

    @staticmethod
    def level_for_overdue(incident: Incident, now: datetime) -> int:
        """Level 2 as soon as the response deadline passes, then one level per response window."""
        if not incident.response_due_at or now <= incident.response_due_at:
            return 1
        window = max((incident.response_due_at - incident.created_at).total_seconds(), 60)
        overdue = (now - incident.response_due_at).total_seconds()
        return min(len(ESCALATION_LEVELS), 2 + int(overdue // window))


@dataclass
class SlaMonitorReport:
    warnings: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    escalations: list[str] = field(default_factory=list)


class SlaMonitor:
    """Scans open incidents; safe to call repeatedly (each flag fires once)."""

    def run(self, now: datetime | None = None) -> SlaMonitorReport:
        now = now or timezone.now()
        report = SlaMonitorReport()
        incidents = Incident.objects.filter(status__in=OPEN_STATUSES).select_related("assignee", "service")
        for incident in incidents:
            self._check_response(incident, now, report)
            self._check_resolution(incident, now, report)
            self._check_escalation(incident, now, report)
        return report

    def _check_response(self, incident, now, report):
        if incident.status not in PRE_ACKNOWLEDGEMENT_STATUSES or not incident.response_due_at:
            return
        progress = _progress(incident.created_at, incident.response_due_at, now)
        if now > incident.response_due_at and not incident.response_breached:
            incident.response_breached = True
            incident.save(update_fields=["response_breached"])
            report.violations.append(incident.code)
            event_bus.publish(DomainEvent("SlaViolated", incident, None, incident.status, incident.status,
                                          f"Response deadline missed on {incident.code}.",
                                          {"kind": "response"}))
        elif progress >= WARNING_THRESHOLD and not incident.response_warning_sent and not incident.response_breached:
            incident.response_warning_sent = True
            incident.save(update_fields=["response_warning_sent"])
            report.warnings.append(incident.code)
            event_bus.publish(DomainEvent("SlaWarningRaised", incident, None, incident.status, incident.status,
                                          f"{incident.code} is close to its response deadline.",
                                          {"kind": "response"}))

    def _check_resolution(self, incident, now, report):
        if not incident.resolution_due_at:
            return
        progress = _progress(incident.created_at, incident.resolution_due_at, now)
        if now > incident.resolution_due_at and not incident.resolution_breached:
            incident.resolution_breached = True
            incident.save(update_fields=["resolution_breached"])
            report.violations.append(incident.code)
            event_bus.publish(DomainEvent("SlaViolated", incident, None, incident.status, incident.status,
                                          f"Resolution deadline missed on {incident.code}.",
                                          {"kind": "resolution"}))
        elif progress >= WARNING_THRESHOLD and not incident.resolution_warning_sent and not incident.resolution_breached:
            incident.resolution_warning_sent = True
            incident.save(update_fields=["resolution_warning_sent"])
            report.warnings.append(incident.code)
            event_bus.publish(DomainEvent("SlaWarningRaised", incident, None, incident.status, incident.status,
                                          f"{incident.code} is close to its resolution deadline.",
                                          {"kind": "resolution"}))

    def _check_escalation(self, incident, now, report):
        if incident.priority not in (IncidentPriority.P1, IncidentPriority.P2):
            return
        if incident.status not in PRE_ACKNOWLEDGEMENT_STATUSES:
            return
        level = EscalationChain.level_for_overdue(incident, now)
        if level > incident.escalation_level:
            incident.escalation_level = level
            incident.save(update_fields=["escalation_level"])
            target = EscalationChain.recipient_for(level, incident)
            report.escalations.append(incident.code)
            event_bus.publish(DomainEvent(
                "IncidentEscalated", incident, None, incident.status, incident.status,
                f"{incident.code} was not acknowledged in time and was escalated to "
                f"{ESCALATION_LEVELS[level - 1].lower()}.",
                {"level": level, "target": target}))

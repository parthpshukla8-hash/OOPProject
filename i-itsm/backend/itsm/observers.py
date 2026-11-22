"""Observers: the audit trail and notification fan-out. Adding a reaction = adding an observer."""
from __future__ import annotations

from .channels import ChannelFactory
from .events import DomainEvent, EventObserver, event_bus
from .models import AuditEvent, User

SUBJECTS = {
    "IncidentReported": "{code} was reported: {title}",
    "TechnicianAssigned": "{code} was assigned to {assignee}",
    "PriorityChanged": "{code} is now {priority}",
    "IncidentAcknowledged": "{assignee} picked up {code}",
    "InformationRequested": "{code} needs more information from you",
    "InformationProvided": "{code}: the reporter replied",
    "IncidentResolved": "{code} was resolved. Please confirm it works",
    "IncidentVerified": "{code} was confirmed fixed by the reporter",
    "IncidentReopened": "{code} was reopened",
    "IncidentClosed": "{code} is closed",
    "SlaWarningRaised": "{code} is close to breaching its SLA",
    "SlaViolated": "{code} breached its SLA",
    "IncidentEscalated": "{code} was escalated to you",
    "RootCauseIdentified": "{code} may be caused by an issue on an upstream service",
    "IncidentJoined": "Another person is affected by {code}",
}


def _administrators():
    return list(User.objects.filter(role=User.Role.ADMINISTRATOR, is_active=True))


def resolve_recipients(event: DomainEvent) -> list[User]:
    incident = event.incident
    if incident is None:
        return []
    reporter, assignee = incident.reporter, incident.assignee
    rules = {
        "IncidentReported": [reporter] + (_administrators() if incident.priority == "P1" else []),
        "TechnicianAssigned": [assignee, reporter],
        "PriorityChanged": [reporter, assignee],
        "IncidentAcknowledged": [reporter],
        "InformationRequested": [reporter],
        "InformationProvided": [assignee],
        "IncidentResolved": [reporter],
        "IncidentVerified": [assignee],
        "IncidentReopened": [assignee],
        "IncidentClosed": [reporter],
        "SlaWarningRaised": [assignee] + _administrators(),
        "SlaViolated": [assignee] + _administrators(),
        "IncidentEscalated": [event.payload.get("target")] + _administrators(),
        "RootCauseIdentified": [assignee],
        "IncidentJoined": [assignee, reporter],
    }
    seen, recipients = set(), []
    for user in rules.get(event.name, []):
        if user and user.pk not in seen and (event.actor is None or user.pk != event.actor.pk):
            seen.add(user.pk)
            recipients.append(user)
    return recipients


class AuditObserver(EventObserver):
    def handle(self, event: DomainEvent) -> None:
        AuditEvent.objects.create(
            incident=event.incident, actor=event.actor, action=event.name,
            previous_state=event.previous_state, new_state=event.new_state, description=event.description)


class NotificationObserver(EventObserver):
    def handle(self, event: DomainEvent) -> None:
        template = SUBJECTS.get(event.name)
        if not template or event.incident is None:
            return
        incident = event.incident
        subject = template.format(
            code=incident.code, title=incident.title, priority=incident.priority,
            assignee=incident.assignee.display_name if incident.assignee_id else "a technician")
        for recipient in resolve_recipients(event):
            for channel in ChannelFactory.for_event(event.name, incident):
                channel.deliver(recipient, incident, subject, event.description or subject)


def register_default_observers() -> None:
    event_bus.subscribe(AuditObserver())
    event_bus.subscribe(NotificationObserver())

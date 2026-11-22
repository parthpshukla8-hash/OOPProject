"""State pattern: each lifecycle state knows its legal successors and its entry rules/side-effects."""
from abc import ABC

from django.utils import timezone

from .events import Event, bus
from .exceptions import InvalidInput, InvalidStateTransition


class IncidentState(ABC):
    name = ""
    next_states = ()

    def can_transition_to(self, target):
        return target in self.next_states

    def validate_entry(self, incident):
        """Business rule guards for entering this state."""

    def on_enter(self, incident, now, previous):
        """Side effects when entering this state."""


class New(IncidentState):
    name, next_states = "NEW", ("CLASSIFIED",)


class Classified(IncidentState):
    name, next_states = "CLASSIFIED", ("ASSIGNED",)


class Assigned(IncidentState):
    name, next_states = "ASSIGNED", ("ACKNOWLEDGED",)

    def validate_entry(self, incident):
        if not incident.assignee_id:
            raise InvalidStateTransition("An incident cannot be ASSIGNED without a technician.")

    def on_enter(self, incident, now, previous):
        incident.assigned_at = now


class Acknowledged(IncidentState):
    name, next_states = "ACKNOWLEDGED", ("IN_PROGRESS",)

    def on_enter(self, incident, now, previous):
        incident.acknowledged_at = now
        if incident.response_due and now > incident.response_due:
            incident.response_breached = True


class InProgress(IncidentState):
    name, next_states = "IN_PROGRESS", ("AWAITING_INFO", "RESOLVED")

    def on_enter(self, incident, now, previous):
        if previous == "RESOLVED":                     # reopened after failed verification
            incident.resolved_at = None


class AwaitingInfo(IncidentState):
    name, next_states = "AWAITING_INFO", ("IN_PROGRESS",)


class Resolved(IncidentState):
    name, next_states = "RESOLVED", ("VERIFIED", "IN_PROGRESS")

    def validate_entry(self, incident):
        if not incident.resolution.strip():
            raise InvalidInput("Resolution details are required to resolve an incident.")

    def on_enter(self, incident, now, previous):
        incident.resolved_at = now
        if incident.resolution_due and now > incident.resolution_due:
            incident.resolution_breached = True


class Verified(IncidentState):
    name, next_states = "VERIFIED", ("CLOSED",)


class Closed(IncidentState):
    name, next_states = "CLOSED", ()

    def on_enter(self, incident, now, previous):
        incident.closed_at = now


STATES = {s.name: s for s in (New(), Classified(), Assigned(), Acknowledged(), InProgress(),
                              AwaitingInfo(), Resolved(), Verified(), Closed())}


def transition(incident, target, actor=None, note="", event_type="STATUS_CHANGED"):
    current = STATES[incident.status]
    if not current.can_transition_to(target):
        raise InvalidStateTransition(f"Illegal transition {incident.status} -> {target}.")
    nxt = STATES[target]
    nxt.validate_entry(incident)
    previous = incident.status
    incident.status = target
    nxt.on_enter(incident, timezone.now(), previous)
    incident.save()
    bus.publish(Event(event_type, incident, actor, note or f"Status changed {previous} -> {target}", previous, target))

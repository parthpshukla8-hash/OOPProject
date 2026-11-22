"""Incident lifecycle (State pattern).

One class per status. Each declares which statuses may follow it, checks the
conditions for entering it, and applies its own side effects (timestamps, SLA
flags). Nothing outside this module decides whether a transition is legal.
"""
from __future__ import annotations

from abc import ABC
from datetime import datetime

from django.utils import timezone

from .exceptions import InvalidStateTransition, InvalidUserInput
from .models import IncidentStatus as S


class IncidentState(ABC):
    status: str = ""
    label: str = ""
    next_statuses: tuple[str, ...] = ()

    def can_transition_to(self, next_status: str) -> bool:
        return next_status in self.next_statuses

    def check_entry(self, incident, context: dict) -> None:
        """Raise if the incident is not ready to enter this state."""

    def on_enter(self, incident, context: dict, now: datetime) -> None:
        """Apply timestamps and flags once the incident enters this state."""


class NewState(IncidentState):
    status, label, next_statuses = S.NEW, "New", (S.CLASSIFIED,)


class ClassifiedState(IncidentState):
    status, label, next_statuses = S.CLASSIFIED, "Classified", (S.ASSIGNED,)


class AssignedState(IncidentState):
    status, label, next_statuses = S.ASSIGNED, "Assigned", (S.ACKNOWLEDGED,)

    def check_entry(self, incident, context):
        if incident.assignee_id is None:
            raise InvalidStateTransition("An incident cannot be assigned without a technician.")


class AcknowledgedState(IncidentState):
    status, label, next_statuses = S.ACKNOWLEDGED, "Acknowledged", (S.IN_PROGRESS,)

    def on_enter(self, incident, context, now):
        incident.acknowledged_at = now
        if incident.response_due_at and now > incident.response_due_at:
            incident.response_breached = True


class InProgressState(IncidentState):
    status, label = S.IN_PROGRESS, "In progress"
    next_statuses = (S.WAITING_FOR_INFO, S.RESOLVED)

    def on_enter(self, incident, context, now):
        if context.get("previous") in (S.RESOLVED, S.VERIFIED):  # reopened
            incident.resolved_at = None
            incident.verified_at = None
            incident.reopen_count += 1


class WaitingForInfoState(IncidentState):
    status, label, next_statuses = S.WAITING_FOR_INFO, "Waiting for information", (S.IN_PROGRESS,)

    def check_entry(self, incident, context):
        if not context.get("question"):
            raise InvalidUserInput("Say what information you need from the reporter.")


class ResolvedState(IncidentState):
    status, label = S.RESOLVED, "Resolved"
    next_statuses = (S.VERIFIED, S.IN_PROGRESS)

    def check_entry(self, incident, context):
        if not (incident.resolution or "").strip():
            raise InvalidUserInput("Describe how the incident was resolved before resolving it.")

    def on_enter(self, incident, context, now):
        incident.resolved_at = now
        if incident.resolution_due_at and now > incident.resolution_due_at:
            incident.resolution_breached = True


class VerifiedState(IncidentState):
    status, label = S.VERIFIED, "Verified"
    next_statuses = (S.CLOSED, S.IN_PROGRESS)

    def on_enter(self, incident, context, now):
        incident.verified_at = now


class ClosedState(IncidentState):
    status, label = S.CLOSED, "Closed"

    def on_enter(self, incident, context, now):
        incident.closed_at = now


STATES: dict[str, IncidentState] = {
    state.status: state for state in (
        NewState(), ClassifiedState(), AssignedState(), AcknowledgedState(), InProgressState(),
        WaitingForInfoState(), ResolvedState(), VerifiedState(), ClosedState(),
    )
}


def get_state(status: str) -> IncidentState:
    return STATES[status]


def transition(incident, next_status: str, now: datetime | None = None, **context) -> str:
    """Move the incident to next_status if legal. Returns the previous status. Does not save."""
    current = get_state(incident.status)
    target = get_state(next_status)
    if not current.can_transition_to(next_status):
        raise InvalidStateTransition(
            f"An incident that is {current.label.lower()} cannot move to {target.label.lower()}.",
            current=current.status, requested=next_status)
    target.check_entry(incident, context)
    previous = incident.status
    incident.status = next_status
    target.on_enter(incident, {**context, "previous": previous}, now or timezone.now())
    return previous

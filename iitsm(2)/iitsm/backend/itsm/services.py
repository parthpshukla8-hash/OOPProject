"""Application services: orchestrate factories, strategies, state machine and events."""
from django.db import transaction
from django.utils import timezone

from .assignment import eligible_technicians, get_assignment_strategy
from .events import Event, bus
from .exceptions import (InvalidInput, InvalidStateTransition, ITSMError, TechnicianUnavailable,
                         UnauthorizedOperation, WorkloadExceeded)
from .factories import IncidentFactory
from . import insights
from .intelligence import find_similar
from .lifecycle import transition
from .models import Category, IncidentComment, User
from .sla import apply_sla

R = User.Role
# action -> (target state, who may perform it, default audit note, comment kind for the message)
ACTIONS = {
    "acknowledge":  ("ACKNOWLEDGED", {"ASSIGNEE", "ADMIN"}, "Technician acknowledged incident", None),
    "start":        ("IN_PROGRESS", {"ASSIGNEE", "ADMIN"}, "Investigation started", None),
    "request_info": ("AWAITING_INFO", {"ASSIGNEE", "ADMIN"}, "Additional information requested from reporter", "INFO_REQUEST"),
    "respond":      ("IN_PROGRESS", {"REPORTER", "ADMIN"}, "Reporter provided requested information", "REPLY"),
    "resolve":      ("RESOLVED", {"ASSIGNEE", "ADMIN"}, "Resolution provided; incident marked RESOLVED", None),
    "verify":       ("VERIFIED", {"REPORTER", "ADMIN"}, "Resolution verified by reporter", None),
    "reopen":       ("IN_PROGRESS", {"REPORTER", "ADMIN"}, "Resolution rejected; incident reopened", "REPLY"),
    "close":        ("CLOSED", {"ASSIGNEE", "ADMIN"}, "Incident closed", None),
}


def _is(actor, inc, who):
    return {"ADMIN": actor.role == R.ADMIN, "ASSIGNEE": inc.assignee_id == actor.id,
            "REPORTER": inc.reporter_id == actor.id}[who]


def _require(actor, inc, allowed):
    if not any(_is(actor, inc, w) for w in allowed):
        raise UnauthorizedOperation("You are not permitted to perform this operation on this incident.")


class IncidentService:
    @staticmethod
    @transaction.atomic
    def create(reporter, data):
        inc = IncidentFactory.build(reporter, data)
        inc.save()
        bus.publish(Event("INCIDENT_CREATED", inc, reporter,
                          f"Incident created by {reporter.role.title()} {reporter.username}", "", "NEW"))
        bus.publish(Event("PRIORITY_CALCULATED", inc, None,
                          f"Priority calculated as {inc.priority} (score {inc.score}); SLA response due {inc.response_due:%H:%M}, "
                          f"resolution due {inc.resolution_due:%H:%M}"))
        transition(inc, "CLASSIFIED", None, f"Incident classified as {inc.category.name.upper()}")
        dups = find_similar(inc.title, inc.description, inc.service_id, exclude_id=inc.pk, threshold=0.5)
        if dups:
            inc.duplicate_of = dups[0][0]
            inc.save(update_fields=["duplicate_of"])
            bus.publish(Event("DUPLICATE_DETECTED", inc, None,
                              f"Possible duplicate of {dups[0][0].number} (similarity {dups[0][1]})"))
        rc = insights.root_cause(inc)
        if rc:
            bus.publish(Event("ROOT_CAUSE_IDENTIFIED", inc, None,
                              f"Probable root cause: upstream service '{rc['service']}' already has open incident(s) {', '.join(rc['incidents'])}"))
        AssignmentService.auto_assign(inc, None)
        return inc

    @staticmethod
    @transaction.atomic
    def update(inc, actor, data):
        if inc.status == "CLOSED":
            raise InvalidStateTransition("Closed incidents cannot be modified.")
        if actor.role == R.EMPLOYEE:
            _require(actor, inc, {"REPORTER"})
            allowed = {"description"}
        elif actor.role == R.TECHNICIAN:
            _require(actor, inc, {"ASSIGNEE"})
            allowed = {"title", "description", "category", "impact", "urgency", "affected_users"}
        else:
            allowed = {"title", "description", "category", "impact", "urgency", "affected_users"}
        changes = {k: v for k, v in data.items() if k in allowed}
        if not changes:
            raise InvalidInput("No editable fields supplied.")
        old_priority, rescore = inc.priority, False
        for k, v in changes.items():
            if k == "category":
                cat = Category.objects.filter(pk=v).first()
                if not cat:
                    raise InvalidInput("Unknown category.")
                inc.category = cat
            elif k in ("impact", "urgency", "affected_users"):
                v = int(v)
                if (k != "affected_users" and not 1 <= v <= 4) or v < 1:
                    raise InvalidInput(f"Invalid value for {k}.")
                setattr(inc, k, v)
                rescore = True
            else:
                setattr(inc, k, v)
        if rescore:
            IncidentFactory.prioritise(inc)
            if inc.priority != old_priority:
                apply_sla(inc, inc.created_at)
        inc.save()
        bus.publish(Event("INCIDENT_UPDATED", inc, actor, f"Incident updated ({', '.join(changes)}) by {actor.username}"))
        if inc.priority != old_priority:
            bus.publish(Event("PRIORITY_CHANGED", inc, actor, f"Priority changed {old_priority} -> {inc.priority}"))
        return inc

    @staticmethod
    @transaction.atomic
    def perform(inc, actor, action, message=""):
        target, allowed, note, kind = ACTIONS[action]
        _require(actor, inc, allowed)
        message = (message or "").strip()
        if action == "resolve":
            if not message:
                raise InvalidInput("Resolution details are required.")
            inc.resolution = message
        elif action in ("request_info", "respond") and not message:
            raise InvalidInput("A message is required.")
        transition(inc, target, actor, note)
        if kind and message:
            IncidentComment.objects.create(incident=inc, author=actor, text=message, kind=kind)
        return inc

    @staticmethod
    @transaction.atomic
    def comment(inc, actor, text, internal=False):
        text = (text or "").strip()
        if not text:
            raise InvalidInput("Comment text is required.")
        if actor.role == R.EMPLOYEE:
            _require(actor, inc, {"REPORTER"})
            internal = False
        elif actor.role == R.TECHNICIAN:
            _require(actor, inc, {"ASSIGNEE"})
        kind = "NOTE" if actor.role != R.EMPLOYEE else "COMMENT"
        c = IncidentComment.objects.create(incident=inc, author=actor, text=text, kind=kind, internal=internal)
        bus.publish(Event("COMMENT_ADDED", inc, actor, f"{'Investigation note' if internal else 'Comment'} added by {actor.username}",
                          internal=internal))
        return c

    @staticmethod
    def feedback(inc, actor, rating, comment=""):
        _require(actor, inc, {"REPORTER"})
        if inc.status not in ("RESOLVED", "VERIFIED", "CLOSED"):
            raise InvalidStateTransition("Feedback can only be given after resolution.")
        if not 1 <= int(rating) <= 5:
            raise InvalidInput("Rating must be between 1 and 5.")
        inc.feedback_rating, inc.feedback_comment = int(rating), comment
        inc.save(update_fields=["feedback_rating", "feedback_comment"])
        bus.publish(Event("FEEDBACK_RECEIVED", inc, actor, f"Feedback received: {rating}/5"))
        return inc


class AssignmentService:
    @staticmethod
    @transaction.atomic
    def assign(inc, technician, actor):
        if technician.role != R.TECHNICIAN:
            raise InvalidInput("Selected user is not a technician.")
        if not technician.is_available:
            raise TechnicianUnavailable(f"{technician.username} is not available.")
        if technician.assigned_incidents.exclude(pk=inc.pk).filter(
                status__in=["ASSIGNED", "ACKNOWLEDGED", "IN_PROGRESS", "AWAITING_INFO"]).count() >= technician.max_load:
            raise WorkloadExceeded(f"{technician.username} has reached the maximum workload ({technician.max_load}).")
        if inc.status not in ("CLASSIFIED", "ASSIGNED"):
            raise InvalidStateTransition(f"Cannot assign an incident in state {inc.status}.")
        technician.last_assigned_at = timezone.now()
        technician.save(update_fields=["last_assigned_at"])
        inc.assignee = technician
        who = actor.username if actor else "system"
        if inc.status == "ASSIGNED":                                  # re-assignment
            inc.save()
            bus.publish(Event("ASSIGNED", inc, actor, f"Re-assigned to Technician {technician.username} by {who}", "ASSIGNED", "ASSIGNED"))
        else:
            transition(inc, "ASSIGNED", actor, f"Assigned to Technician {technician.username} by {who}", event_type="ASSIGNED")
        return inc

    @staticmethod
    def auto_assign(inc, actor):
        try:
            strategy = get_assignment_strategy()
            tech = strategy.pick(inc, eligible_technicians())
            return AssignmentService.assign(inc, tech, actor)
        except ITSMError as e:
            bus.publish(Event("ASSIGNMENT_FAILED", inc, None, f"Automatic assignment failed: {e.detail}. Awaiting manual assignment."))
            return inc

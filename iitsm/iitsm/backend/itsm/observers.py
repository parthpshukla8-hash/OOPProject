"""Observers subscribed to the event bus: audit trail + notifications."""
from .channels import ChannelFactory
from .models import AuditLog, User

SILENT_STATES = {"CLASSIFIED"}                     # audit only, no notification
SLA_EVENTS = {"SLA_WARNING", "SLA_BREACHED", "ESCALATED", "ASSIGNMENT_FAILED", "ROOT_CAUSE_IDENTIFIED"}
NOTIFY = {                                         # event type -> channels
    "INCIDENT_CREATED": ["IN_APP"], "ASSIGNED": ["IN_APP", "EMAIL"], "PRIORITY_CHANGED": ["IN_APP"],
    "COMMENT_ADDED": ["IN_APP"], "DUPLICATE_DETECTED": ["IN_APP"], "SLA_WARNING": ["IN_APP", "EMAIL"],
    "SLA_BREACHED": ["IN_APP", "EMAIL", "SMS"], "ESCALATED": ["IN_APP", "EMAIL", "SMS"],
    "ASSIGNMENT_FAILED": ["IN_APP"], "ROOT_CAUSE_IDENTIFIED": ["IN_APP"],
}


class AuditObserver:
    def handle(self, e):
        AuditLog.objects.create(incident=e.incident, user=e.actor, action=e.type,
                                previous_state=e.previous_state, new_state=e.new_state, description=e.description)


class NotificationObserver:
    def channels_for(self, e):
        if e.type == "STATUS_CHANGED":
            if e.new_state in SILENT_STATES:
                return []
            return ["IN_APP", "EMAIL"] if e.new_state in ("RESOLVED", "CLOSED") else ["IN_APP"]
        return NOTIFY.get(e.type, [])

    def recipients(self, e):
        inc, people = e.incident, set()
        if e.type in SLA_EVENTS or (e.type == "INCIDENT_CREATED" and inc.priority == "P1"):
            people.update(User.objects.filter(role=User.Role.ADMIN, is_active=True))
        if e.type not in ("ASSIGNMENT_FAILED",):
            people.add(inc.reporter)
            if inc.assignee:
                people.add(inc.assignee)
        if e.type == "COMMENT_ADDED" and getattr(e, "internal", False):
            people.discard(inc.reporter)
        people.discard(e.actor)
        return people

    def handle(self, e):
        channels = self.channels_for(e)
        if not channels:
            return
        msg = f"{e.incident.number}: {e.description}"
        for person in self.recipients(e):
            for ch in channels:
                ChannelFactory.get(ch).send(person, e.incident, msg)

"""Use cases. Views call these; these call the domain modules and publish events."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Callable

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .assignment import get_assignment_strategy, pick_technician
from .events import DomainEvent, event_bus
from .exceptions import (DuplicateIncident, InvalidStateTransition, InvalidUserInput, TechnicianUnavailable,
                         TechnicianWorkloadExceeded, UnauthorizedOperation)
from .factories import IncidentFactory
from .insights import find_probable_root_cause
from .intelligence import (EXACT_REPEAT_THRESHOLD, detect_duplicates, find_similar_incidents,
                           suggest_category, suggest_resolutions, suggest_service)
from .lifecycle import transition
from .models import (Category, FINISHED_STATUSES, Incident, IncidentComment, IncidentPriority,
                     IncidentStatus as S, Service, User, WORKING_STATUSES)
from .priority import calculate_incident_priority
from .similarity import SimilarityIndex
from .sla import SlaStatus, apply_sla_deadlines, check_sla_compliance


# ---------------------------------------------------------------- visibility and permissions

def visible_incidents(user: User):
    """Queryset scoping: employees see their own, technicians their assigned ones, admins everything."""
    queryset = Incident.objects.select_related("reporter", "assignee", "service", "category")
    if user.is_administrator:
        return queryset
    if user.is_technician:
        return queryset.filter(Q(assignee=user) | Q(reporter=user))
    return queryset.filter(Q(reporter=user) | Q(also_affected=user)).distinct()


def can_view(user: User, incident: Incident) -> bool:
    return visible_incidents(user).filter(pk=incident.pk).exists()


def _is_staff_for(user: User, incident: Incident) -> bool:
    return user.is_administrator or (user.is_technician and incident.assignee_id == user.pk)


def _is_reporter_or_admin(user: User, incident: Incident) -> bool:
    return user.is_administrator or incident.reporter_id == user.pk


def _is_involved(user: User, incident: Incident) -> bool:
    return _is_staff_for(user, incident) or incident.reporter_id == user.pk


@dataclass(frozen=True)
class ActionSpec:
    key: str
    label: str
    from_statuses: tuple[str, ...]
    target: str
    event: str
    allowed: Callable[[User, Incident], bool]
    needs: str | None = None          # name of the text field the user must supply
    needs_label: str = ""
    primary: bool = True


ACTIONS: dict[str, ActionSpec] = {spec.key: spec for spec in (
    ActionSpec("acknowledge", "Acknowledge", (S.ASSIGNED,), S.ACKNOWLEDGED, "IncidentAcknowledged", _is_staff_for),
    ActionSpec("start", "Start investigating", (S.ACKNOWLEDGED,), S.IN_PROGRESS, "InvestigationStarted", _is_staff_for),
    ActionSpec("request_info", "Ask the reporter", (S.IN_PROGRESS,), S.WAITING_FOR_INFO, "InformationRequested",
               _is_staff_for, "question", "What do you need to know?", primary=False),
    ActionSpec("provide_info", "Send reply", (S.WAITING_FOR_INFO,), S.IN_PROGRESS, "InformationProvided",
               lambda u, i: i.reporter_id == u.pk, "body", "Your reply"),
    ActionSpec("resolve", "Mark resolved", (S.IN_PROGRESS,), S.RESOLVED, "IncidentResolved", _is_staff_for,
               "resolution", "What fixed it?"),
    ActionSpec("verify", "It works now", (S.RESOLVED,), S.VERIFIED, "IncidentVerified", _is_reporter_or_admin),
    ActionSpec("reopen", "Not fixed", (S.RESOLVED, S.VERIFIED), S.IN_PROGRESS, "IncidentReopened", _is_involved,
               "reason", "What is still wrong?", primary=False),
    ActionSpec("close", "Close incident", (S.VERIFIED,), S.CLOSED, "IncidentClosed", _is_staff_for),
)}


def available_actions(incident: Incident, user: User) -> list[dict]:
    """Only the steps this person can take right now: the UI renders exactly this list."""
    actions = [
        {"key": s.key, "label": s.label, "needs": s.needs, "needs_label": s.needs_label, "primary": s.primary}
        for s in ACTIONS.values() if incident.status in s.from_statuses and s.allowed(user, incident)
    ]
    if (user.is_employee and incident.is_open and incident.reporter_id != user.pk
            and not incident.also_affected.filter(pk=user.pk).exists()):
        actions.append({"key": "join", "label": "I'm affected too", "needs": None, "needs_label": "", "primary": True})
    if user.is_administrator and incident.status in (S.CLASSIFIED, *WORKING_STATUSES):
        actions.append({"key": "assign", "label": "Assign", "needs": "technician", "needs_label": "",
                        "primary": False})
    if (incident.reporter_id == user.pk and incident.status in FINISHED_STATUSES
            and incident.feedback_rating is None):
        actions.append({"key": "feedback", "label": "Rate the fix", "needs": "rating", "needs_label": "",
                        "primary": False})
    return actions


# ---------------------------------------------------------------- analysis (live help while reporting)

def analyze_report(user: User, title: str, description: str, service_id: int | None = None,
                   impact: int | None = None, urgency: int | None = None, affected_users: int = 1) -> dict:
    """Everything the report form needs to be context-aware, from partial input."""
    text = f"{title or ''} {description or ''}".strip()
    if len(text) < 8:
        return {"categories": [], "services": [], "similar": [], "resolutions": [], "priority": None}
    services = suggest_service(text)
    service = Service.objects.filter(pk=service_id).first() if service_id else (
        Service.objects.filter(pk=services[0]["id"]).first() if services else None)
    similar = find_similar_incidents(text, service, limit=3)
    priority = None
    if impact and urgency and service:
        result = calculate_incident_priority(int(impact), int(urgency), service, max(int(affected_users or 1), 1))
        priority = {"priority": result.priority, "score": result.score, "rationale": list(result.rationale)}
    return {
        "categories": suggest_category(text),
        "services": services,
        "similar": [{
            "id": m.incident.pk, "code": m.incident.code, "title": m.incident.title, "status": m.incident.status,
            "priority": m.incident.priority, "service": m.incident.service.name if m.incident.service_id else None,
            "score": m.score, "level": m.level, "matched_terms": list(m.shared_terms),
            "reported_by_me": m.incident.reporter_id == user.pk,
            "already_joined": m.incident.also_affected.filter(pk=user.pk).exists(),
            "created_at": m.incident.created_at,
        } for m in similar],
        "resolutions": suggest_resolutions(text, limit=2),
        "priority": priority,
    }


# ---------------------------------------------------------------- incident use cases

def _publish(name, incident, actor=None, previous="", new="", description="", **payload):
    event_bus.publish(DomainEvent(name, incident, actor, previous, new or incident.status, description, payload))


def _refresh_priority(incident: Incident, actor: User | None) -> bool:
    """Recalculate priority and SLA deadlines. Returns True if the priority band changed."""
    previous = incident.priority
    result = calculate_incident_priority(incident.impact, incident.urgency, incident.service, incident.affected_users)
    incident.priority_score, incident.priority = result.score, result.priority
    incident.priority_rationale = list(result.rationale)
    apply_sla_deadlines(incident)
    incident.save()
    if previous != incident.priority:
        _publish("PriorityChanged", incident, actor, description=f"Priority changed from {previous} to "
                 f"{incident.priority}. {'; '.join(result.rationale)}")
        return True
    return False


@transaction.atomic
def create_incident(reporter: User, title: str, description: str, impact: int, urgency: int,
                    affected_users: int = 1, service_id: int | None = None,
                    category_id: int | None = None) -> Incident:
    incident = IncidentFactory.build(reporter, title, description, impact, urgency, affected_users,
                                     service_id, category_id)
    repeat = [m for m in find_similar_incidents(f"{incident.title} {incident.description}", incident.service,
                                                within_days=1)
              if m.incident.reporter_id == reporter.pk and m.text_score >= EXACT_REPEAT_THRESHOLD]
    if repeat:
        raise DuplicateIncident(f"You already reported this as {repeat[0].incident.code} and it is still open.",
                                existing_id=repeat[0].incident.pk, existing_code=repeat[0].incident.code)

    incident.save()
    apply_sla_deadlines(incident)
    incident.save(update_fields=["response_due_at", "resolution_due_at"])
    _publish("IncidentReported", incident, reporter, "", S.NEW,
             f"{incident.code} reported by {reporter.display_name}: {incident.title}")

    previous = transition(incident, S.CLASSIFIED)
    incident.save()
    _publish("IncidentClassified", incident, None, previous, S.CLASSIFIED,
             f"Classified as {incident.category.name if incident.category_id else 'uncategorised'} on "
             f"{incident.service.name}. Priority {incident.priority} ({'; '.join(incident.priority_rationale)}).")

    matches = detect_duplicates(incident)
    likely = [m for m in matches if m.level == "likely_duplicate"]
    if likely:
        incident.duplicate_of = likely[0].incident
        incident.save(update_fields=["duplicate_of"])
        _publish("DuplicateFlagged", incident, None, description=(
            f"Looks like {likely[0].incident.code} (text similarity {likely[0].text_score:.2f}, matched on "
            f"{', '.join(likely[0].shared_terms)})."))

    try:
        best = pick_technician(incident)
        assign_incident(incident, best.technician, actor=None, automatic=True)
    except (TechnicianUnavailable, TechnicianWorkloadExceeded) as error:
        _publish("AssignmentPending", incident, None, description=f"Could not assign automatically: {error.message}")

    cause = find_probable_root_cause(incident)
    if cause:
        incident.probable_root_cause = cause
        incident.save(update_fields=["probable_root_cause"])
        _publish("RootCauseIdentified", incident, None, description=(
            f"{cause.code} on {cause.service.name} is open and {incident.service.name} relies on it."))
    return incident


@transaction.atomic
def assign_incident(incident: Incident, technician: User, actor: User | None = None,
                    automatic: bool = False) -> Incident:
    if actor is not None and not actor.is_administrator:
        raise UnauthorizedOperation("Only administrators can assign incidents.")
    if not technician.is_technician or not technician.is_active:
        raise InvalidUserInput("Incidents can only be assigned to active technicians.")
    if not technician.is_available:
        raise TechnicianUnavailable(f"{technician.display_name} is marked as unavailable.")
    if incident.assignee_id != technician.pk and technician.active_incident_count >= technician.max_active_incidents:
        raise TechnicianWorkloadExceeded(f"{technician.display_name} is already at {technician.max_active_incidents} "
                                         "active incidents.")
    previous_status = incident.status
    if incident.status == S.CLASSIFIED:
        incident.assignee = technician
        transition(incident, S.ASSIGNED)
    elif incident.status in WORKING_STATUSES:
        incident.assignee = technician
        if incident.status == S.ASSIGNED:
            incident.escalation_level = 1
    else:
        raise InvalidStateTransition("This incident can no longer be assigned.")
    incident.save()
    how = f"automatically ({get_assignment_strategy().label.lower()})" if automatic else f"by {actor.display_name}"
    _publish("TechnicianAssigned", incident, actor, previous_status, incident.status,
             f"Assigned to {technician.display_name} {how}.")
    return incident


@transaction.atomic
def update_incident(incident: Incident, actor: User, data: dict) -> Incident:
    if incident.status in (S.RESOLVED, S.VERIFIED, S.CLOSED):
        raise InvalidStateTransition("A resolved or closed incident can no longer be edited.")
    is_staff = _is_staff_for(actor, incident)
    if not (is_staff or (incident.reporter_id == actor.pk and incident.status in (S.NEW, S.CLASSIFIED, S.ASSIGNED))):
        raise UnauthorizedOperation("You cannot edit this incident any more. Add a comment instead.")
    allowed = {"title", "description", "impact", "urgency", "affected_users"}
    if is_staff:
        allowed |= {"category", "service"}
    changes = []
    for field in allowed & data.keys():
        value = data[field]
        if field in ("impact", "urgency") and not (isinstance(value, int) and 1 <= value <= 4):
            raise InvalidUserInput(f"{field.capitalize()} must be a number from 1 to 4.")
        if field == "affected_users" and not (isinstance(value, int) and value >= 1):
            raise InvalidUserInput("The number of affected users must be at least 1.")
        if field in ("title", "description"):
            value = (value or "").strip()
            if len(value) < (5 if field == "title" else 10):
                raise InvalidUserInput(f"The {field} is too short.")
        if field == "category":
            value = Category.objects.filter(pk=value).first()
            if value is None:
                raise InvalidUserInput("That category does not exist.")
        if field == "service":
            value = Service.objects.filter(pk=value, is_active=True).first()
            if value is None:
                from .exceptions import ServiceNotFound
                raise ServiceNotFound()
        if getattr(incident, field) != value:
            changes.append(f"{field.replace('_', ' ')} changed from {getattr(incident, field)} to {value}")
            setattr(incident, field, value)
    if not changes:
        return incident
    priority_changed = _refresh_priority(incident, actor)
    if not priority_changed:
        _publish("IncidentUpdated", incident, actor, description="; ".join(changes))
    return incident


@transaction.atomic
def perform_action(incident: Incident, action: str, actor: User, payload: dict | None = None) -> Incident:
    payload = payload or {}
    if action == "join":
        return join_incident(incident, actor)
    spec = ACTIONS.get(action)
    if spec is None:
        raise InvalidUserInput(f"Unknown action '{action}'.")
    if not spec.allowed(actor, incident):
        raise UnauthorizedOperation("You are not allowed to do that on this incident.")
    text = (payload.get(spec.needs) or "").strip() if spec.needs else ""
    if spec.needs and not text:
        raise InvalidUserInput(f"{spec.needs_label or spec.needs.capitalize()} is required.")
    if spec.key == "resolve":
        incident.resolution = text
    context = {"question": text} if spec.key == "request_info" else {}
    previous = transition(incident, spec.target, **context)
    incident.save()
    if spec.key in ("request_info", "provide_info"):
        kind = IncidentComment.Kind.INFO_REQUEST if spec.key == "request_info" else IncidentComment.Kind.INFO_REPLY
        IncidentComment.objects.create(incident=incident, author=actor, kind=kind, body=text)
    if spec.key == "reopen":
        IncidentComment.objects.create(incident=incident, author=actor, body=f"Reopened: {text}")
    descriptions = {
        "resolve": f"Resolved by {actor.display_name}: {text}",
        "request_info": f"{actor.display_name} asked: {text}",
        "provide_info": f"{actor.display_name} replied: {text}",
        "reopen": f"Reopened by {actor.display_name}: {text}",
    }
    _publish(spec.event, incident, actor, previous, incident.status,
             descriptions.get(spec.key, f"{spec.label} by {actor.display_name}."))
    return incident


@transaction.atomic
def join_incident(incident: Incident, actor: User) -> Incident:
    if not actor.is_employee:
        raise UnauthorizedOperation("Only employees can add themselves to an incident.")
    if not incident.is_open:
        raise InvalidStateTransition("This incident is no longer open.")
    if incident.reporter_id == actor.pk or incident.also_affected.filter(pk=actor.pk).exists():
        raise InvalidUserInput("You are already part of this incident.")
    incident.also_affected.add(actor)
    incident.affected_users += 1
    IncidentComment.objects.create(incident=incident, author=actor, kind=IncidentComment.Kind.JOINED,
                                   body=f"{actor.display_name} is affected too.")
    incident.save(update_fields=["affected_users"])
    _publish("IncidentJoined", incident, actor, description=f"{actor.display_name} reported being affected too.")
    _refresh_priority(incident, actor)
    return incident


@transaction.atomic
def add_comment(incident: Incident, actor: User, body: str, internal: bool = False) -> IncidentComment:
    body = (body or "").strip()
    if not body:
        raise InvalidUserInput("Write something first.")
    if incident.status == S.CLOSED:
        raise InvalidStateTransition("Closed incidents cannot be commented on.")
    if internal and not (actor.is_administrator or actor.is_technician):
        raise UnauthorizedOperation("Only staff can add internal notes.")
    if not can_view(actor, incident):
        raise UnauthorizedOperation()
    comment = IncidentComment.objects.create(incident=incident, author=actor, body=body, is_internal=internal)
    _publish("NoteAdded", incident, actor, description=f"{'Internal note' if internal else 'Comment'} by "
             f"{actor.display_name}: {body[:120]}")
    return comment


@transaction.atomic
def submit_feedback(incident: Incident, actor: User, rating: int, comment: str = "") -> Incident:
    if incident.reporter_id != actor.pk:
        raise UnauthorizedOperation("Only the reporter can rate the resolution.")
    if incident.status not in FINISHED_STATUSES:
        raise InvalidStateTransition("You can rate the fix once the incident is resolved.")
    if incident.feedback_rating is not None:
        raise InvalidUserInput("You already rated this incident.")
    if not isinstance(rating, int) or not 1 <= rating <= 5:
        raise InvalidUserInput("The rating must be a number from 1 to 5.")
    incident.feedback_rating, incident.feedback_comment = rating, (comment or "").strip()
    incident.save(update_fields=["feedback_rating", "feedback_comment"])
    _publish("FeedbackSubmitted", incident, actor, description=f"Rated {rating} out of 5.")
    return incident


# ---------------------------------------------------------------- search

def search_incidents(user: User, params: dict, limit: int = 200) -> list[Incident]:
    queryset = visible_incidents(user)
    if params.get("status"):
        queryset = queryset.filter(status__in=params["status"].split(","))
    if params.get("priority"):
        queryset = queryset.filter(priority__in=params["priority"].split(","))
    for param, field in (("category", "category_id"), ("service", "service_id"), ("technician", "assignee_id")):
        if params.get(param):
            queryset = queryset.filter(**{field: params[param]})
    for param, lookup in (("date_from", "created_at__gte"), ("date_to", "created_at__lte")):
        if params.get(param):
            try:
                day = datetime.strptime(params[param], "%Y-%m-%d").date()
            except ValueError:
                raise InvalidUserInput("Dates must look like 2026-11-21.")
            boundary = datetime.combine(day, time.min if param == "date_from" else time.max)
            queryset = queryset.filter(**{lookup: timezone.make_aware(boundary)})
    if params.get("scope") == "open":
        queryset = queryset.exclude(status__in=FINISHED_STATUSES)
    elif params.get("scope") == "finished":
        queryset = queryset.filter(status__in=FINISHED_STATUSES)
    if params.get("mine") == "assigned":
        queryset = queryset.filter(assignee=user)
    elif params.get("mine") == "reported":
        queryset = queryset.filter(Q(reporter=user) | Q(also_affected=user)).distinct()

    incidents = list(queryset.order_by("-created_at")[:1000])
    text = (params.get("q") or "").strip()
    if text:
        code = re.fullmatch(r"(?i)(?:inc)?0*(\d+)", text)
        if code:
            incidents = [i for i in incidents if i.pk == int(code.group(1))]
        else:
            index = SimilarityIndex([(i, f"{i.title} {i.description} {i.resolution}") for i in incidents])
            scores = {m.item.pk: m.score for m in index.search(text, limit=len(incidents))}
            lowered = text.lower()
            for i in incidents:
                i.search_score = scores.get(i.pk, 0.0) + (0.3 if lowered in i.title.lower() else 0.0)
            incidents = sorted((i for i in incidents if i.search_score > 0.05), key=lambda i: -i.search_score)
    if params.get("sla_status"):
        wanted = params["sla_status"].split(",")
        incidents = [i for i in incidents if check_sla_compliance(i).status.value in wanted]
    if not text:
        order = {p: n for n, p in enumerate(IncidentPriority.values)}
        if user.is_employee:
            incidents.sort(key=lambda i: i.updated_at, reverse=True)
        else:
            incidents.sort(key=lambda i: (not i.is_open, order[i.priority],
                                          i.resolution_due_at or timezone.now() + timedelta(days=365)))
    return incidents[:limit]

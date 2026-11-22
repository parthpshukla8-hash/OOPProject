"""Factory pattern: centralised, validated creation of users and incidents."""
from datetime import timedelta

from django.utils import timezone

from .exceptions import DuplicateIncident, InvalidInput, ServiceNotFound
from .insights import effective_criticality
from .intelligence import suggest_category
from .models import DONE_STATUSES, Category, Incident, Service, User
from .priority import get_priority_strategy
from .sla import apply_sla


class UserFactory:
    @staticmethod
    def create(role, username, password, **extra):
        if role not in User.Role.values:
            raise InvalidInput(f"Unknown role '{role}'.")
        if len(password or "") < 6:
            raise InvalidInput("Password must be at least 6 characters.")
        extra.setdefault("is_staff", role == User.Role.ADMIN)
        if role != User.Role.TECHNICIAN:
            for k in ("experience_years", "max_load", "is_available"):
                extra.pop(k, None)
        return User.objects.create_user(username=username, password=password, role=role, **extra)


class IncidentFactory:
    @staticmethod
    def build(reporter, data):
        title, description = (data.get("title") or "").strip(), (data.get("description") or "").strip()
        if not title or not description:
            raise InvalidInput("Title and description are required.")
        service = Service.objects.filter(pk=data.get("service")).first()
        if service is None:
            raise ServiceNotFound("The affected service does not exist.")
        category = Category.objects.filter(pk=data.get("category")).first() if data.get("category") else None
        if category is None:
            category, _ = suggest_category(f"{title} {description}")
        if category is None:
            category = Category.objects.filter(name__iexact="Application").first() or Category.objects.first()
        if category is None:
            raise InvalidInput("No incident categories are configured.")
        recent = Incident.objects.filter(reporter=reporter, title__iexact=title, created_at__gte=timezone.now() - timedelta(minutes=5)) \
            .exclude(status__in=DONE_STATUSES)
        if recent.exists():
            raise DuplicateIncident(f"You already reported this incident ({recent.first().number}).")

        impact, urgency = int(data.get("impact", 2)), int(data.get("urgency", 2))
        users = int(data.get("affected_users", 1))
        if not (1 <= impact <= 4 and 1 <= urgency <= 4) or users < 1:
            raise InvalidInput("Impact and urgency must be 1-4 and affected users at least 1.")
        inc = Incident(title=title, description=description, reporter=reporter, category=category, service=service,
                       impact=impact, urgency=urgency, affected_users=users)
        IncidentFactory.prioritise(inc)
        apply_sla(inc, timezone.now())
        return inc

    @staticmethod
    def prioritise(inc):
        inc.score, inc.priority = get_priority_strategy().calculate(
            inc.impact, inc.urgency, effective_criticality(inc.service), inc.affected_users)

"""Factory pattern: validated construction of users and incidents."""
from __future__ import annotations

import re

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .exceptions import InvalidUserInput, ServiceNotFound
from .intelligence import suggest_category, suggest_service
from .models import Category, Incident, Service, User
from .priority import calculate_incident_priority
from .sla import find_sla_policy

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,150}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_TITLE_LENGTH, MIN_DESCRIPTION_LENGTH = 5, 10


class UserFactory:
    @staticmethod
    def create(username: str, password: str, role: str = User.Role.EMPLOYEE, first_name: str = "",
               last_name: str = "", email: str = "", phone: str = "", skills=None, experience_years: int = 0,
               team_lead: User | None = None, is_it_manager: bool = False,
               max_active_incidents: int = 6) -> User:
        if not USERNAME_PATTERN.match(username or ""):
            raise InvalidUserInput("Usernames need 3 or more letters, numbers, dots, dashes or underscores.")
        if User.objects.filter(username__iexact=username).exists():
            raise InvalidUserInput("That username is already taken.")
        if role not in User.Role.values:
            raise InvalidUserInput(f"Unknown role '{role}'.")
        if email and not EMAIL_PATTERN.match(email):
            raise InvalidUserInput("That email address does not look right.")
        try:
            validate_password(password)
        except ValidationError as error:
            raise InvalidUserInput(" ".join(error.messages))
        user = User(username=username, role=role, first_name=first_name, last_name=last_name, email=email,
                    phone=phone, experience_years=experience_years, team_lead=team_lead,
                    is_it_manager=is_it_manager, max_active_incidents=max_active_incidents,
                    is_staff=role == User.Role.ADMINISTRATOR)
        user.set_password(password)  # hashed, never stored in plain text
        user.save()
        if skills:
            user.skills.set(skills)
        return user


class IncidentFactory:
    @classmethod
    def build(cls, reporter: User, title: str, description: str, impact: int, urgency: int,
              affected_users: int = 1, service_id: int | None = None, category_id: int | None = None) -> Incident:
        title, description = (title or "").strip(), (description or "").strip()
        if len(title) < MIN_TITLE_LENGTH or len(title) > 140:
            raise InvalidUserInput(f"The title needs between {MIN_TITLE_LENGTH} and 140 characters.")
        if len(description) < MIN_DESCRIPTION_LENGTH:
            raise InvalidUserInput("Describe what is happening in a little more detail.")
        for label, value in (("Impact", impact), ("Urgency", urgency)):
            if not isinstance(value, int) or not 1 <= value <= 4:
                raise InvalidUserInput(f"{label} must be a number from 1 to 4.")
        if not isinstance(affected_users, int) or affected_users < 1:
            raise InvalidUserInput("The number of affected users must be at least 1.")

        text = f"{title} {description}"
        service, category = cls.resolve_classification(text, service_id, category_id)
        result = calculate_incident_priority(impact, urgency, service, affected_users)
        find_sla_policy(result.priority, service)  # fail early if no SLA is configured

        return Incident(reporter=reporter, title=title, description=description, service=service,
                        category=category, impact=impact, urgency=urgency, affected_users=affected_users,
                        priority=result.priority, priority_score=result.score,
                        priority_rationale=list(result.rationale))

    @classmethod
    def resolve_classification(cls, text: str, service_id: int | None = None,
                               category_id: int | None = None) -> tuple[Service, Category | None]:
        service = cls._resolve_service(service_id, text)
        category = cls._resolve_category(category_id, text, service)
        return service, category

    @staticmethod
    def _resolve_service(service_id, text) -> Service:
        if service_id:
            service = Service.objects.filter(pk=service_id, is_active=True).first()
            if service is None:
                raise ServiceNotFound()
            return service
        suggestions = suggest_service(text, limit=1)
        if suggestions:
            return Service.objects.get(pk=suggestions[0]["id"])
        fallback = Service.objects.filter(name=settings.GENERAL_SERVICE_NAME, is_active=True).first()
        if fallback is None:
            raise ServiceNotFound("Choose the affected service. It could not be worked out from the description.")
        return fallback

    @staticmethod
    def _resolve_category(category_id, text, service: Service) -> Category | None:
        if category_id:
            category = Category.objects.filter(pk=category_id).first()
            if category is None:
                raise InvalidUserInput("That category does not exist.")
            return category
        suggestions = suggest_category(text, limit=1)
        if suggestions:
            return Category.objects.get(pk=suggestions[0]["id"])
        return service.default_category or Category.objects.filter(name=settings.GENERAL_CATEGORY_NAME).first()

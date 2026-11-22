from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class IncidentStatus(models.TextChoices):
    NEW = "NEW", "New"
    CLASSIFIED = "CLASSIFIED", "Classified"
    ASSIGNED = "ASSIGNED", "Assigned"
    ACKNOWLEDGED = "ACKNOWLEDGED", "Acknowledged"
    IN_PROGRESS = "IN_PROGRESS", "In progress"
    WAITING_FOR_INFO = "WAITING_FOR_INFO", "Waiting for information"
    RESOLVED = "RESOLVED", "Resolved"
    VERIFIED = "VERIFIED", "Verified"
    CLOSED = "CLOSED", "Closed"


class IncidentPriority(models.TextChoices):
    P1 = "P1", "Critical"
    P2 = "P2", "High"
    P3 = "P3", "Medium"
    P4 = "P4", "Low"


# Statuses in which the incident still needs work (the SLA clock is running).
OPEN_STATUSES = (
    IncidentStatus.NEW, IncidentStatus.CLASSIFIED, IncidentStatus.ASSIGNED,
    IncidentStatus.ACKNOWLEDGED, IncidentStatus.IN_PROGRESS, IncidentStatus.WAITING_FOR_INFO,
)
# Statuses in which a technician is actively holding the incident.
WORKING_STATUSES = (
    IncidentStatus.ASSIGNED, IncidentStatus.ACKNOWLEDGED,
    IncidentStatus.IN_PROGRESS, IncidentStatus.WAITING_FOR_INFO,
)
FINISHED_STATUSES = (IncidentStatus.RESOLVED, IncidentStatus.VERIFIED, IncidentStatus.CLOSED)


class User(AbstractUser):
    class Role(models.TextChoices):
        EMPLOYEE = "EMPLOYEE", "Employee"
        TECHNICIAN = "TECHNICIAN", "Technician"
        ADMINISTRATOR = "ADMINISTRATOR", "Administrator"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.EMPLOYEE)
    phone = models.CharField(max_length=20, blank=True)
    skills = models.ManyToManyField("Category", blank=True, related_name="skilled_technicians")
    experience_years = models.PositiveSmallIntegerField(default=0)
    max_active_incidents = models.PositiveSmallIntegerField(default=6)
    is_available = models.BooleanField(default=True)
    team_lead = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name="team_members")
    is_it_manager = models.BooleanField(default=False)

    @property
    def is_employee(self) -> bool:
        return self.role == self.Role.EMPLOYEE

    @property
    def is_technician(self) -> bool:
        return self.role == self.Role.TECHNICIAN

    @property
    def is_administrator(self) -> bool:
        return self.role == self.Role.ADMINISTRATOR

    @property
    def display_name(self) -> str:
        return self.get_full_name() or self.username

    @property
    def active_incident_count(self) -> int:
        return self.assigned_incidents.filter(status__in=WORKING_STATUSES).count()

    def __str__(self):
        return f"{self.display_name} ({self.username})"


class Category(models.Model):
    name = models.CharField(max_length=60, unique=True)
    description = models.CharField(max_length=200, blank=True)
    keywords = models.TextField(blank=True, help_text="Words that typically appear in this kind of incident.")

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Service(models.Model):
    name = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=240, blank=True)
    keywords = models.TextField(blank=True)
    business_criticality = models.PositiveSmallIntegerField(
        default=3, validators=[MinValueValidator(1), MaxValueValidator(5)])
    default_category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL,
                                         related_name="default_for_services")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ServiceDependency(models.Model):
    """`service` relies on `depends_on` (e.g. Payment relies on Core Database)."""
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="dependencies")
    depends_on = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="dependents")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["service", "depends_on"], name="unique_service_dependency")]


class SlaPolicy(models.Model):
    """Response and resolution targets per priority; a service-specific row overrides the default."""
    priority = models.CharField(max_length=2, choices=IncidentPriority.choices)
    service = models.ForeignKey(Service, null=True, blank=True, on_delete=models.CASCADE,
                                related_name="sla_policies")
    response_minutes = models.PositiveIntegerField()
    resolution_minutes = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["priority", "service"], name="unique_sla_policy_per_service"),
            models.UniqueConstraint(fields=["priority"], condition=Q(service__isnull=True),
                                    name="unique_default_sla_policy_per_priority"),
        ]
        ordering = ["priority"]


class SystemConfiguration(models.Model):
    """Single row holding the strategies the administrator can switch at runtime."""
    assignment_strategy = models.CharField(max_length=30, default="smart")
    priority_strategy = models.CharField(max_length=30, default="weighted")
    round_robin_cursor = models.PositiveIntegerField(default=0)
    last_sla_check_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def current(cls) -> "SystemConfiguration":
        configuration, _ = cls.objects.get_or_create(pk=1)
        return configuration


class Incident(models.Model):
    reporter = models.ForeignKey(User, on_delete=models.PROTECT, related_name="reported_incidents")
    assignee = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="assigned_incidents")
    title = models.CharField(max_length=140)
    description = models.TextField()
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="incidents")
    service = models.ForeignKey(Service, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="incidents")
    impact = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(4)])
    urgency = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(4)])
    affected_users = models.PositiveIntegerField(default=1)
    priority_score = models.FloatField(default=0)
    priority = models.CharField(max_length=2, choices=IncidentPriority.choices, default=IncidentPriority.P4)
    priority_rationale = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=IncidentStatus.choices, default=IncidentStatus.NEW)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    response_due_at = models.DateTimeField(null=True, blank=True)
    resolution_due_at = models.DateTimeField(null=True, blank=True)
    response_breached = models.BooleanField(default=False)
    resolution_breached = models.BooleanField(default=False)
    response_warning_sent = models.BooleanField(default=False)
    resolution_warning_sent = models.BooleanField(default=False)
    escalation_level = models.PositiveSmallIntegerField(default=1)

    resolution = models.TextField(blank=True)
    reopen_count = models.PositiveSmallIntegerField(default=0)
    feedback_rating = models.PositiveSmallIntegerField(null=True, blank=True,
                                                       validators=[MinValueValidator(1), MaxValueValidator(5)])
    feedback_comment = models.TextField(blank=True)

    duplicate_of = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="duplicates")
    probable_root_cause = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL,
                                            related_name="probable_effects")
    also_affected = models.ManyToManyField(User, blank=True, related_name="joined_incidents")

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status"]), models.Index(fields=["priority"])]

    @property
    def code(self) -> str:
        return f"INC{self.pk:04d}" if self.pk else "INC----"

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    @property
    def search_text(self) -> str:
        parts = [self.title, self.description]
        if self.service_id:
            parts.append(self.service.name)
        return " ".join(parts)

    def __str__(self):
        return f"{self.code} {self.title}"
    


class IncidentComment(models.Model):
    class Kind(models.TextChoices):
        NOTE = "NOTE", "Note"
        INFO_REQUEST = "INFO_REQUEST", "Information request"
        INFO_REPLY = "INFO_REPLY", "Information reply"
        JOINED = "JOINED", "Also affected"

    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(User, on_delete=models.PROTECT, related_name="incident_comments")
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.NOTE)
    body = models.TextField()
    is_internal = models.BooleanField(default=False, help_text="Investigation notes visible to staff only.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class AuditEvent(models.Model):
    incident = models.ForeignKey(Incident, null=True, blank=True, on_delete=models.CASCADE,
                                 related_name="audit_events")
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=60)
    previous_state = models.CharField(max_length=20, blank=True)
    new_state = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class Notification(models.Model):
    class Channel(models.TextChoices):
        IN_APP = "IN_APP", "In-app"
        EMAIL = "EMAIL", "Email"
        SMS = "SMS", "SMS"

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    incident = models.ForeignKey(Incident, null=True, blank=True, on_delete=models.CASCADE,
                                 related_name="notifications")
    channel = models.CharField(max_length=10, choices=Channel.choices, default=Channel.IN_APP)
    subject = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

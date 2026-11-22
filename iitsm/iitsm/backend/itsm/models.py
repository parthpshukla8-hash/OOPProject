from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Count, Q


class Status(models.TextChoices):
    NEW = "NEW", "New"
    CLASSIFIED = "CLASSIFIED", "Classified"
    ASSIGNED = "ASSIGNED", "Assigned"
    ACKNOWLEDGED = "ACKNOWLEDGED", "Acknowledged"
    IN_PROGRESS = "IN_PROGRESS", "In progress"
    AWAITING_INFO = "AWAITING_INFO", "Awaiting info"
    RESOLVED = "RESOLVED", "Resolved"
    VERIFIED = "VERIFIED", "Verified"
    CLOSED = "CLOSED", "Closed"


ACTIVE_STATUSES = ["ASSIGNED", "ACKNOWLEDGED", "IN_PROGRESS", "AWAITING_INFO"]   # counts toward technician load
DONE_STATUSES = ["RESOLVED", "VERIFIED", "CLOSED"]                                # SLA clock stopped


class User(AbstractUser):
    class Role(models.TextChoices):
        EMPLOYEE = "EMPLOYEE", "Employee"
        TECHNICIAN = "TECHNICIAN", "Technician"
        ADMIN = "ADMIN", "Administrator"

    role = models.CharField(max_length=12, choices=Role.choices, default=Role.EMPLOYEE)
    # technician-only attributes
    skills = models.ManyToManyField("Category", blank=True, related_name="technicians")
    experience_years = models.PositiveSmallIntegerField(default=0)
    max_load = models.PositiveSmallIntegerField(default=5)
    is_available = models.BooleanField(default=True)
    last_assigned_at = models.DateTimeField(null=True, blank=True)

    @property
    def active_load(self):
        cached = getattr(self, "load_count", None)       # set by annotated pool queries
        if cached is not None:
            return cached
        return self.assigned_incidents.filter(status__in=ACTIVE_STATUSES).count()

    @property
    def display_name(self):
        return self.get_full_name() or self.username


class Category(models.Model):
    name = models.CharField(max_length=60, unique=True)
    keywords = models.TextField(blank=True, help_text="Comma-separated keywords used for auto-categorisation")

    def __str__(self):
        return self.name


class Service(models.Model):
    name = models.CharField(max_length=80, unique=True)
    description = models.TextField(blank=True)
    business_criticality = models.PositiveSmallIntegerField(default=3, help_text="1 (low) – 5 (mission critical)")

    def __str__(self):
        return self.name


class SLAPolicy(models.Model):
    """Per-priority SLA. A policy with service=None is the default; a service-specific one overrides it."""
    service = models.ForeignKey(Service, null=True, blank=True, on_delete=models.CASCADE, related_name="sla_policies")
    priority = models.CharField(max_length=2, choices=[("P1", "P1"), ("P2", "P2"), ("P3", "P3"), ("P4", "P4")])
    response_minutes = models.PositiveIntegerField()
    resolution_minutes = models.PositiveIntegerField()

    class Meta:
        unique_together = ("service", "priority")


class SystemSetting(models.Model):
    ASSIGNMENT = [("SKILL", "Skill based"), ("LOAD", "Load based"), ("ROUND_ROBIN", "Round robin"),
                  ("SMART", "Smart (skills + load + experience + history)")]
    PRIORITY = [("WEIGHTED", "Weighted score"), ("RULE", "Rule based (weighted + critical-service override)")]
    assignment_strategy = models.CharField(max_length=12, choices=ASSIGNMENT, default="SMART")
    priority_strategy = models.CharField(max_length=10, choices=PRIORITY, default="WEIGHTED")

    @classmethod
    def load(cls):
        return cls.objects.get_or_create(pk=1)[0]


class Incident(models.Model):
    number = models.CharField(max_length=12, unique=True, null=True, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    reporter = models.ForeignKey(User, on_delete=models.PROTECT, related_name="reported_incidents")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="incidents")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="incidents")
    impact = models.PositiveSmallIntegerField(default=2)        # 1-4
    urgency = models.PositiveSmallIntegerField(default=2)       # 1-4
    affected_users = models.PositiveIntegerField(default=1)
    score = models.FloatField(default=0)
    priority = models.CharField(max_length=2, default="P4")
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.NEW)
    assignee = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_incidents")
    duplicate_of = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="duplicates")

    created_at = models.DateTimeField(auto_now_add=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    response_due = models.DateTimeField(null=True, blank=True)
    resolution_due = models.DateTimeField(null=True, blank=True)
    response_breached = models.BooleanField(default=False)
    resolution_breached = models.BooleanField(default=False)
    warning_sent = models.BooleanField(default=False)
    escalation_level = models.PositiveSmallIntegerField(default=0)

    resolution = models.TextField(blank=True)
    feedback_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    feedback_comment = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.number:
            self.number = f"INC{1000 + self.pk}"
            super().save(update_fields=["number"])

    def __str__(self):
        return f"{self.number} {self.title}"


class IncidentComment(models.Model):
    KINDS = [("NOTE", "Investigation note"), ("INFO_REQUEST", "Info request"),
             ("REPLY", "Reply"), ("COMMENT", "Comment")]
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(User, on_delete=models.PROTECT)
    text = models.TextField()
    kind = models.CharField(max_length=14, choices=KINDS, default="COMMENT")
    internal = models.BooleanField(default=False)   # hidden from the reporter
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class AuditLog(models.Model):
    incident = models.ForeignKey(Incident, null=True, blank=True, on_delete=models.CASCADE, related_name="audit")
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)   # null = system
    action = models.CharField(max_length=40)
    previous_state = models.CharField(max_length=14, blank=True)
    new_state = models.CharField(max_length=14, blank=True)
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp", "id"]


class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    incident = models.ForeignKey(Incident, null=True, blank=True, on_delete=models.CASCADE)
    channel = models.CharField(max_length=10, default="IN_APP")   # IN_APP / EMAIL / SMS (last two simulated)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


def technician_pool():
    """Active technicians annotated with their current load (single query)."""
    return (User.objects.filter(role=User.Role.TECHNICIAN, is_active=True)
            .annotate(load_count=Count("assigned_incidents", filter=Q(assigned_incidents__status__in=ACTIVE_STATUSES)))
            .prefetch_related("skills"))


class ServiceDependency(models.Model):
    """`service` depends on `depends_on` (e.g. Payment -> Database Cluster)."""
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="dependencies")
    depends_on = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="dependents")

    class Meta:
        unique_together = ("service", "depends_on")

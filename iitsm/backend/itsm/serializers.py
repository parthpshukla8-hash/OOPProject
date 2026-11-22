from rest_framework import serializers

from . import sla
from .factories import UserFactory
from .models import (AuditLog, Category, Incident, IncidentComment, Notification, Service, SLAPolicy,
                     SystemSetting, User)


def brief(u):
    return {"id": u.id, "username": u.username, "name": u.display_name, "role": u.role} if u else None


class UserSerializer(serializers.ModelSerializer):
    """Read-only profile (used for /auth/me and technician lists)."""
    active_load = serializers.IntegerField(read_only=True)
    name = serializers.CharField(source="display_name", read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "name", "email", "role", "skills", "experience_years", "max_load",
                  "is_available", "active_load"]


class UserAdminSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6, required=False)

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email", "role", "skills", "experience_years",
                  "max_load", "is_available", "is_active", "password"]

    def validate(self, data):
        if self.instance is None and not data.get("password"):
            raise serializers.ValidationError({"password": "Password is required."})
        return data

    def create(self, vd):
        skills, pwd, role = vd.pop("skills", []), vd.pop("password"), vd.pop("role", "EMPLOYEE")
        user = UserFactory.create(role, vd.pop("username"), pwd, **vd)
        user.skills.set(skills)
        return user

    def update(self, inst, vd):
        pwd = vd.pop("password", None)
        inst = super().update(inst, vd)
        if pwd:
            inst.set_password(pwd)
            inst.save()
        return inst


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(min_length=6, write_only=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)

    def validate_username(self, v):
        if User.objects.filter(username__iexact=v).exists():
            raise serializers.ValidationError("Username already taken.")
        return v


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "keywords"]


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ["id", "name", "description", "business_criticality"]

    def validate_business_criticality(self, v):
        if not 1 <= v <= 5:
            raise serializers.ValidationError("Must be between 1 and 5.")
        return v


class SLAPolicySerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source="service.name", read_only=True, default="(default)")

    class Meta:
        model = SLAPolicy
        fields = ["id", "service", "service_name", "priority", "response_minutes", "resolution_minutes"]


class SettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSetting
        fields = ["assignment_strategy", "priority_strategy"]


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()

    class Meta:
        model = IncidentComment
        fields = ["id", "author", "text", "kind", "internal", "created_at"]

    def get_author(self, c):
        return brief(c.author)


class AuditSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    incident_number = serializers.CharField(source="incident.number", read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = ["id", "timestamp", "user", "action", "incident", "incident_number", "previous_state", "new_state", "description"]

    def get_user(self, a):
        return a.user.username if a.user else "system"


class NotificationSerializer(serializers.ModelSerializer):
    incident_number = serializers.CharField(source="incident.number", read_only=True, default=None)

    class Meta:
        model = Notification
        fields = ["id", "incident", "incident_number", "channel", "message", "is_read", "created_at"]


class IncidentSerializer(serializers.ModelSerializer):
    reporter = serializers.SerializerMethodField()
    assignee = serializers.SerializerMethodField()
    category_name = serializers.CharField(source="category.name", read_only=True)
    service_name = serializers.CharField(source="service.name", read_only=True)
    duplicate_of_number = serializers.CharField(source="duplicate_of.number", read_only=True, default=None)
    sla_status = serializers.SerializerMethodField()
    sla_risk = serializers.SerializerMethodField()
    escalation = serializers.SerializerMethodField()

    class Meta:
        model = Incident
        fields = ["id", "number", "title", "description", "reporter", "category", "category_name", "service",
                  "service_name", "impact", "urgency", "affected_users", "score", "priority", "status", "assignee",
                  "created_at", "assigned_at", "acknowledged_at", "resolved_at", "closed_at", "response_due",
                  "resolution_due", "response_breached", "resolution_breached", "escalation_level", "escalation",
                  "resolution", "feedback_rating", "feedback_comment", "duplicate_of", "duplicate_of_number",
                  "sla_status", "sla_risk"]

    def get_reporter(self, i):
        return brief(i.reporter)

    def get_assignee(self, i):
        return brief(i.assignee)

    def get_sla_status(self, i):
        return sla.sla_status(i)

    def get_sla_risk(self, i):
        return sla.risk(i)

    def get_escalation(self, i):
        return sla.ESCALATION_CHAIN[i.escalation_level] if i.escalation_level else None


class IncidentDetailSerializer(IncidentSerializer):
    comments = serializers.SerializerMethodField()
    history = serializers.SerializerMethodField()

    class Meta(IncidentSerializer.Meta):
        fields = IncidentSerializer.Meta.fields + ["comments", "history"]

    def get_comments(self, i):
        qs = i.comments.select_related("author")
        if self.context["request"].user.role == "EMPLOYEE":
            qs = qs.filter(internal=False)
        return CommentSerializer(qs, many=True).data

    def get_history(self, i):
        return AuditSerializer(i.audit.select_related("user"), many=True).data


class IncidentCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    description = serializers.CharField()
    service = serializers.IntegerField()
    category = serializers.IntegerField(required=False, allow_null=True)
    impact = serializers.IntegerField(min_value=1, max_value=4, default=2)
    urgency = serializers.IntegerField(min_value=1, max_value=4, default=2)
    affected_users = serializers.IntegerField(min_value=1, default=1)

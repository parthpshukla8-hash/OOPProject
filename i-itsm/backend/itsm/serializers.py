from rest_framework import serializers

from .assignment import ASSIGNMENT_STRATEGIES
from .insights import predict_sla_breach
from .models import (AuditEvent, Category, Incident, IncidentComment, Notification, Service, ServiceDependency,
                     SlaPolicy, User)
from .priority import PRIORITY_STRATEGIES
from .services import available_actions
from .sla import ESCALATION_LEVELS, check_sla_compliance


class UserSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    skill_ids = serializers.PrimaryKeyRelatedField(source="skills", many=True, queryset=Category.objects.all(),
                                                   required=False)
    active_incident_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "display_name", "email", "phone", "role",
                  "is_active", "is_available", "experience_years", "max_active_incidents", "skill_ids",
                  "team_lead", "is_it_manager", "active_incident_count"]
        read_only_fields = ["id", "username", "role", "display_name", "active_incident_count"]


class PersonSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "display_name", "role"]


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "description", "keywords"]


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ["id", "name", "description", "keywords", "business_criticality", "default_category", "is_active"]


class ServiceDependencySerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDependency
        fields = ["id", "service", "depends_on"]


class SlaPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = SlaPolicy
        fields = ["id", "priority", "service", "response_minutes", "resolution_minutes"]


class CommentSerializer(serializers.ModelSerializer):
    author = PersonSerializer(read_only=True)

    class Meta:
        model = IncidentComment
        fields = ["id", "author", "kind", "body", "is_internal", "created_at"]


class AuditEventSerializer(serializers.ModelSerializer):
    actor = PersonSerializer(read_only=True)
    incident_code = serializers.SerializerMethodField()

    class Meta:
        model = AuditEvent
        fields = ["id", "incident", "incident_code", "actor", "action", "previous_state", "new_state",
                  "description", "created_at"]

    def get_incident_code(self, obj):
        return obj.incident.code if obj.incident_id else None


class NotificationSerializer(serializers.ModelSerializer):
    incident_code = serializers.SerializerMethodField()
    recipient_name = serializers.CharField(source="recipient.display_name", read_only=True)

    class Meta:
        model = Notification
        fields = ["id", "incident", "incident_code", "channel", "recipient_name", "subject", "body", "is_read",
                  "created_at"]

    def get_incident_code(self, obj):
        return obj.incident.code if obj.incident_id else None


class IncidentSerializer(serializers.ModelSerializer):
    code = serializers.CharField(read_only=True)
    reporter = PersonSerializer(read_only=True)
    assignee = PersonSerializer(read_only=True)
    service_name = serializers.CharField(source="service.name", read_only=True, default=None)
    category_name = serializers.CharField(source="category.name", read_only=True, default=None)
    sla = serializers.SerializerMethodField()
    search_score = serializers.SerializerMethodField()

    class Meta:
        model = Incident
        fields = ["id", "code", "title", "status", "priority", "reporter", "assignee", "service", "service_name",
                  "category", "category_name", "affected_users", "created_at", "updated_at", "response_due_at",
                  "resolution_due_at", "escalation_level", "sla", "search_score"]

    def get_sla(self, obj):
        snapshot = check_sla_compliance(obj)
        return {"status": snapshot.status.value, "response_progress": snapshot.response_progress,
                "resolution_progress": snapshot.resolution_progress,
                "minutes_to_resolution_due": snapshot.minutes_to_resolution_due}

    def get_search_score(self, obj):
        return getattr(obj, "search_score", None)


class IncidentDetailSerializer(IncidentSerializer):
    comments = serializers.SerializerMethodField()
    available_actions = serializers.SerializerMethodField()
    prediction = serializers.SerializerMethodField()
    duplicate_of_code = serializers.SerializerMethodField()
    probable_root_cause_detail = serializers.SerializerMethodField()
    escalation_label = serializers.SerializerMethodField()
    also_affected_count = serializers.SerializerMethodField()

    class Meta(IncidentSerializer.Meta):
        fields = IncidentSerializer.Meta.fields + [
            "description", "impact", "urgency", "priority_score", "priority_rationale", "resolution",
            "acknowledged_at", "resolved_at", "verified_at", "closed_at", "reopen_count", "feedback_rating",
            "feedback_comment", "comments", "available_actions", "prediction", "duplicate_of",
            "duplicate_of_code", "probable_root_cause_detail", "escalation_label", "also_affected_count"]

    def _user(self):
        return self.context["request"].user

    def get_comments(self, obj):
        comments = obj.comments.select_related("author")
        if self._user().is_employee:
            comments = comments.filter(is_internal=False)
        return CommentSerializer(comments, many=True).data

    def get_available_actions(self, obj):
        return available_actions(obj, self._user())

    def get_prediction(self, obj):
        return None if self._user().is_employee else predict_sla_breach(obj)

    def get_duplicate_of_code(self, obj):
        return obj.duplicate_of.code if obj.duplicate_of_id and not self._user().is_employee else None

    def get_probable_root_cause_detail(self, obj):
        cause = obj.probable_root_cause
        if not cause or self._user().is_employee:
            return None
        return {"id": cause.pk, "code": cause.code, "title": cause.title, "service": cause.service.name}

    def get_escalation_label(self, obj):
        return ESCALATION_LEVELS[obj.escalation_level - 1]

    def get_also_affected_count(self, obj):
        return obj.also_affected.count()


STRATEGY_CATALOG = {
    "assignment": [{"key": s.key, "label": s.label, "description": s.description}
                   for s in ASSIGNMENT_STRATEGIES.values()],
    "priority": [{"key": s.key, "label": s.label, "description": s.description}
                 for s in PRIORITY_STRATEGIES.values()],
}

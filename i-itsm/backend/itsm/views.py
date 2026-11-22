from django.contrib.auth import authenticate
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import reports, services
from .assignment import recommend_technicians, ASSIGNMENT_STRATEGIES
from .exceptions import (IncidentNotFound, InvalidCredentials, InvalidUserInput, UnauthorizedOperation)
from .factories import UserFactory
from .insights import add_dependency, downstream_distances, service_health, upstream_distances
from .intelligence import suggest_resolutions, find_similar_incidents
from .models import (AuditEvent, Category, Incident, Notification, Service, ServiceDependency, SlaPolicy,
                     SystemConfiguration, User)
from .permissions import IsAdministrator, IsAdministratorOrReadOnly, IsStaffMember
from .priority import PRIORITY_STRATEGIES
from .serializers import (AuditEventSerializer, CategorySerializer, IncidentDetailSerializer, IncidentSerializer,
                          NotificationSerializer, ServiceDependencySerializer, ServiceSerializer,
                          SlaPolicySerializer, STRATEGY_CATALOG, UserSerializer)


def _token_response(user, http_status=status.HTTP_200_OK):
    token, _ = Token.objects.get_or_create(user=user)
    return Response({"token": token.key, "user": UserSerializer(user).data}, status=http_status)


# ------------------------------------------------------------------ authentication

class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        user = authenticate(username=request.data.get("username", ""), password=request.data.get("password", ""))
        if user is None:
            raise InvalidCredentials()
        return _token_response(user)


class RegisterView(APIView):
    """Self-registration is for employees only. Staff accounts are created by administrators."""
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        data = request.data
        user = UserFactory.create(
            username=data.get("username", ""), password=data.get("password", ""), role=User.Role.EMPLOYEE,
            first_name=data.get("first_name", ""), last_name=data.get("last_name", ""),
            email=data.get("email", ""), phone=data.get("phone", ""))
        return _token_response(user, status.HTTP_201_CREATED)


class LogoutView(APIView):
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        """People may only change their own availability here; everything else is an administrator task."""
        if "is_available" in request.data:
            request.user.is_available = bool(request.data["is_available"])
            request.user.save(update_fields=["is_available"])
        return Response(UserSerializer(request.user).data)


# ------------------------------------------------------------------ incidents

class IncidentViewSet(viewsets.ViewSet):
    def _incident(self, request, pk) -> Incident:
        incident = services.visible_incidents(request.user).filter(pk=pk).first()
        if incident is None:
            raise IncidentNotFound()
        return incident

    def _detail(self, request, incident):
        return Response(IncidentDetailSerializer(incident, context={"request": request}).data)

    def list(self, request):
        incidents = services.search_incidents(request.user, request.query_params.dict())
        return Response(IncidentSerializer(incidents, many=True, context={"request": request}).data)

    def create(self, request):
        data = request.data
        incident = services.create_incident(
            request.user, data.get("title", ""), data.get("description", ""), data.get("impact"),
            data.get("urgency"), data.get("affected_users", 1), data.get("service"), data.get("category"))
        incident.refresh_from_db()
        return Response(IncidentDetailSerializer(incident, context={"request": request}).data,
                        status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        return self._detail(request, self._incident(request, pk))

    def partial_update(self, request, pk=None):
        incident = services.update_incident(self._incident(request, pk), request.user, request.data)
        return self._detail(request, incident)

    @action(detail=False, methods=["post"])
    def analyze(self, request):
        """Live suggestions while an incident is being written."""
        data = request.data
        return Response(services.analyze_report(
            request.user, data.get("title", ""), data.get("description", ""), data.get("service") or None,
            data.get("impact"), data.get("urgency"), data.get("affected_users") or 1))

    @action(detail=True, methods=["post"], url_path="actions")
    def run_action(self, request, pk=None):
        incident = self._incident(request, pk)
        name = request.data.get("action", "")
        if name == "assign":
            return self.assign(request, pk)
        if name == "feedback":
            return self.feedback(request, pk)
        incident = services.perform_action(incident, name, request.user, request.data)
        return self._detail(request, incident)

    @action(detail=True, methods=["post"])
    def comments(self, request, pk=None):
        incident = self._incident(request, pk)
        services.add_comment(incident, request.user, request.data.get("body", ""),
                             bool(request.data.get("is_internal")))
        return self._detail(request, incident)

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        incident = self._incident(request, pk)
        technician = User.objects.filter(pk=request.data.get("technician"), role=User.Role.TECHNICIAN).first()
        if technician is None:
            raise InvalidUserInput("Choose a technician.")
        services.assign_incident(incident, technician, request.user)
        return self._detail(request, incident)

    @action(detail=True, methods=["post"])
    def feedback(self, request, pk=None):
        incident = self._incident(request, pk)
        services.submit_feedback(incident, request.user, request.data.get("rating"), request.data.get("comment", ""))
        return self._detail(request, incident)

    @action(detail=True, methods=["get"])
    def audit(self, request, pk=None):
        incident = self._incident(request, pk)
        if request.user.is_employee:
            raise UnauthorizedOperation("The audit trail is only available to staff.")
        events = incident.audit_events.select_related("actor", "incident")
        return Response(AuditEventSerializer(events, many=True).data)

    @action(detail=True, methods=["get"])
    def insights(self, request, pk=None):
        """Staff-only: similar incidents, past resolutions and who is best placed to take it."""
        incident = self._incident(request, pk)
        if request.user.is_employee:
            raise UnauthorizedOperation()
        text = f"{incident.title} {incident.description}"
        similar = find_similar_incidents(text, incident.service, exclude_pk=incident.pk, only_open=False, limit=4)
        try:
            recommendations = [{"technician": {"id": r.technician.pk, "display_name": r.technician.display_name},
                                "score": r.score, "reasons": list(r.reasons)}
                               for r in recommend_technicians(incident, ASSIGNMENT_STRATEGIES["smart"], limit=3)]
        except Exception as error:  # nobody available: still show the rest
            recommendations = []
        return Response({
            "similar": [{"id": m.incident.pk, "code": m.incident.code, "title": m.incident.title,
                         "status": m.incident.status, "score": m.score, "level": m.level,
                         "matched_terms": list(m.shared_terms)} for m in similar],
            "resolutions": suggest_resolutions(text, exclude_pk=incident.pk),
            "recommendations": recommendations,
        })


# ------------------------------------------------------------------ reference data

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdministratorOrReadOnly]


class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    permission_classes = [IsAdministratorOrReadOnly]


class SlaPolicyViewSet(viewsets.ModelViewSet):
    queryset = SlaPolicy.objects.all()
    serializer_class = SlaPolicySerializer
    permission_classes = [IsAdministratorOrReadOnly]


class ServiceDependencyViewSet(viewsets.ModelViewSet):
    queryset = ServiceDependency.objects.all()
    serializer_class = ServiceDependencySerializer
    permission_classes = [IsAdministratorOrReadOnly]

    def create(self, request):
        service = Service.objects.filter(pk=request.data.get("service")).first()
        depends_on = Service.objects.filter(pk=request.data.get("depends_on")).first()
        if not service or not depends_on:
            raise InvalidUserInput("Choose both services.")
        dependency = add_dependency(service, depends_on)
        return Response(ServiceDependencySerializer(dependency).data, status=status.HTTP_201_CREATED)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by("role", "username")
    serializer_class = UserSerializer
    permission_classes = [IsAdministrator]

    def create(self, request):
        data = request.data
        user = UserFactory.create(
            username=data.get("username", ""), password=data.get("password", ""),
            role=data.get("role", User.Role.EMPLOYEE), first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""), email=data.get("email", ""), phone=data.get("phone", ""),
            skills=data.get("skill_ids"), experience_years=int(data.get("experience_years") or 0),
            team_lead=User.objects.filter(pk=data.get("team_lead")).first(),
            is_it_manager=bool(data.get("is_it_manager")))
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        if user.pk == request.user.pk:
            raise InvalidUserInput("You cannot deactivate your own account.")
        user.is_active = False  # soft delete keeps incident history intact
        user.save(update_fields=["is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class TechnicianWorkloadView(APIView):
    permission_classes = [IsAdministrator]

    def get(self, request):
        return Response(reports.technician_workload())


class SystemSettingsView(APIView):
    permission_classes = [IsStaffMember]

    def get(self, request):
        configuration = SystemConfiguration.current()
        return Response({"assignment_strategy": configuration.assignment_strategy,
                         "priority_strategy": configuration.priority_strategy, "options": STRATEGY_CATALOG})

    def put(self, request):
        if not request.user.is_administrator:
            raise UnauthorizedOperation()
        configuration = SystemConfiguration.current()
        assignment = request.data.get("assignment_strategy", configuration.assignment_strategy)
        priority = request.data.get("priority_strategy", configuration.priority_strategy)
        if assignment not in ASSIGNMENT_STRATEGIES or priority not in PRIORITY_STRATEGIES:
            raise InvalidUserInput("Unknown strategy.")
        configuration.assignment_strategy, configuration.priority_strategy = assignment, priority
        configuration.save(update_fields=["assignment_strategy", "priority_strategy"])
        return self.get(request)


# ------------------------------------------------------------------ notifications, audit, reports

class NotificationViewSet(viewsets.ViewSet):
    def list(self, request):
        queryset = Notification.objects.filter(recipient=request.user, channel=Notification.Channel.IN_APP)
        return Response(NotificationSerializer(queryset.select_related("incident")[:50], many=True).data)

    @action(detail=False, methods=["get"])
    def outbox(self, request):
        """Simulated email and SMS messages, for demonstration. Administrators only."""
        if not request.user.is_administrator:
            raise UnauthorizedOperation()
        queryset = Notification.objects.exclude(channel=Notification.Channel.IN_APP).select_related("incident")[:100]
        return Response(NotificationSerializer(queryset, many=True).data)

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        Notification.objects.filter(pk=pk, recipient=request.user).update(is_read=True)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AuditEventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditEventSerializer
    permission_classes = [IsAdministrator]

    def get_queryset(self):
        queryset = AuditEvent.objects.select_related("actor", "incident").order_by("-created_at", "-id")
        for param, field in (("incident", "incident_id"), ("action", "action"), ("actor", "actor_id")):
            if self.request.query_params.get(param):
                queryset = queryset.filter(**{field: self.request.query_params[param]})
        return queryset[:300]


class ReportView(APIView):
    permission_classes = [IsAdministrator]

    def get(self, request):
        reports.run_sla_monitor_if_due()
        return Response(reports.full_report())


class SituationView(APIView):
    permission_classes = [IsAdministrator]

    def get(self, request):
        return Response(reports.situation())


class ServiceMapView(APIView):
    permission_classes = [IsStaffMember]

    def get(self, request):
        return Response(service_health())


class SlaCheckView(APIView):
    permission_classes = [IsAdministrator]

    def post(self, request):
        report = reports.run_sla_monitor_if_due(force=True)
        return Response({"warnings": report.warnings, "violations": report.violations,
                         "escalations": report.escalations})

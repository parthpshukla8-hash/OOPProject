from django.contrib.auth import authenticate
from django.db.models import Avg, Count, F, Q
from rest_framework import mixins, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import intelligence, sla
from .assignment import SmartRecommendation, eligible_technicians
from .exceptions import InvalidInput, UnauthorizedOperation
from .factories import UserFactory
from .models import (DONE_STATUSES, AuditLog, Category, Incident, Notification, Service, SLAPolicy, SystemSetting,
                     User, technician_pool)
from .permissions import IsAdmin, IsAdminOrReadOnly
from .serializers import (AuditSerializer, CategorySerializer, IncidentCreateSerializer, IncidentDetailSerializer,
                          IncidentSerializer, NotificationSerializer, RegisterSerializer, ServiceSerializer,
                          SettingSerializer, SLAPolicySerializer, UserAdminSerializer, UserSerializer)
from .services import ACTIONS, AssignmentService, IncidentService


# ---------------------------------------------------------------- auth
@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    user = authenticate(username=request.data.get("username"), password=request.data.get("password"))
    if not user or not user.is_active:
        return Response({"detail": "Invalid username or password.", "code": "invalid_login"}, status=401)
    token, _ = Token.objects.get_or_create(user=user)
    return Response({"token": token.key, "user": UserSerializer(user).data})


@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    s = RegisterSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    d = s.validated_data
    user = UserFactory.create("EMPLOYEE", d["username"], d["password"], first_name=d.get("first_name", ""),
                              last_name=d.get("last_name", ""), email=d.get("email", ""))
    token, _ = Token.objects.get_or_create(user=user)
    return Response({"token": token.key, "user": UserSerializer(user).data}, status=201)


@api_view(["GET"])
def me(request):
    return Response(UserSerializer(request.user).data)


@api_view(["POST"])
def toggle_availability(request):
    if request.user.role != "TECHNICIAN":
        raise UnauthorizedOperation("Only technicians have availability.")
    request.user.is_available = not request.user.is_available
    request.user.save(update_fields=["is_available"])
    return Response(UserSerializer(request.user).data)


# ---------------------------------------------------------------- incidents
class IncidentViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_serializer_class(self):
        return IncidentDetailSerializer if self.action == "retrieve" else IncidentSerializer

    def get_queryset(self):
        u = self.request.user
        qs = Incident.objects.select_related("reporter", "assignee", "category", "service", "duplicate_of")
        if u.role == "EMPLOYEE":
            qs = qs.filter(reporter=u)
        elif u.role == "TECHNICIAN":
            qs = qs.filter(assignee=u)
        if self.action != "list":
            return qs
        p = self.request.query_params
        if p.get("q"):
            qs = qs.filter(Q(number__icontains=p["q"]) | Q(title__icontains=p["q"]) | Q(description__icontains=p["q"]))
        for param, field in (("status", "status"), ("priority", "priority"), ("category", "category_id"),
                             ("service", "service_id"), ("technician", "assignee_id")):
            if p.get(param):
                qs = qs.filter(**{field: p[param]})
        if p.get("date_from"):
            qs = qs.filter(created_at__date__gte=p["date_from"])
        if p.get("date_to"):
            qs = qs.filter(created_at__date__lte=p["date_to"])
        if p.get("sla_status"):
            qs = qs.filter(pk__in=[i.pk for i in qs if sla.sla_status(i) == p["sla_status"]])
        return qs

    def create(self, request):
        s = IncidentCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        inc = IncidentService.create(request.user, s.validated_data)
        return Response(IncidentSerializer(inc).data, status=201)

    def partial_update(self, request, pk=None):
        inc = IncidentService.update(self.get_object(), request.user, request.data)
        return Response(IncidentSerializer(inc).data)

    def _act(self, request, name):
        inc = IncidentService.perform(self.get_object(), request.user, name, request.data.get("message", ""))
        return Response(IncidentSerializer(inc).data)

    @action(detail=True, methods=["post"])
    def acknowledge(self, request, pk=None): return self._act(request, "acknowledge")

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None): return self._act(request, "start")

    @action(detail=True, methods=["post"], url_path="request-info")
    def request_info(self, request, pk=None): return self._act(request, "request_info")

    @action(detail=True, methods=["post"])
    def respond(self, request, pk=None): return self._act(request, "respond")

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None): return self._act(request, "resolve")

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None): return self._act(request, "verify")

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None): return self._act(request, "reopen")

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None): return self._act(request, "close")

    @action(detail=True, methods=["post"])
    def comment(self, request, pk=None):
        IncidentService.comment(self.get_object(), request.user, request.data.get("text"), bool(request.data.get("internal")))
        return Response(IncidentDetailSerializer(self.get_object(), context={"request": request}).data, status=201)

    @action(detail=True, methods=["post"])
    def feedback(self, request, pk=None):
        inc = IncidentService.feedback(self.get_object(), request.user, request.data.get("rating", 0), request.data.get("comment", ""))
        return Response(IncidentSerializer(inc).data)

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        if request.user.role != "ADMIN":
            raise UnauthorizedOperation("Only administrators can assign incidents.")
        inc = self.get_object()
        tid = request.data.get("technician")
        if tid:
            tech = User.objects.filter(pk=tid, role="TECHNICIAN").first()
            if not tech:
                raise InvalidInput("Technician not found.")
            AssignmentService.assign(inc, tech, request.user)
        else:
            AssignmentService.auto_assign(inc, request.user)
        return Response(IncidentSerializer(inc).data)

    @action(detail=True, methods=["get"])
    def recommendations(self, request, pk=None):
        """Smart technician recommendation: ranked list with score breakdown."""
        if request.user.role != "ADMIN":
            raise UnauthorizedOperation("Only administrators can view recommendations.")
        rows = SmartRecommendation().rank(self.get_object(), eligible_technicians())
        return Response([{"technician": UserSerializer(r["technician"]).data, "score": r["score"],
                          "breakdown": r["breakdown"]} for r in rows])

    @action(detail=True, methods=["get"])
    def similar(self, request, pk=None):
        inc = self.get_object()
        if request.user.role == "EMPLOYEE":
            raise UnauthorizedOperation("Not available to employees.")
        hits = intelligence.find_similar(inc.title, inc.description, inc.service_id, exclude_id=inc.pk, open_only=False)
        return Response([{"id": i.id, "number": i.number, "title": i.title, "status": i.status, "score": s} for i, s in hits])

    @action(detail=True, methods=["get"])
    def suggestions(self, request, pk=None):
        if request.user.role == "EMPLOYEE":
            raise UnauthorizedOperation("Not available to employees.")
        return Response(intelligence.suggest_resolutions(self.get_object()))

    @action(detail=False, methods=["post"])
    def suggest(self, request):
        """Live help while reporting: suggested category + possible duplicates (all roles)."""
        title, desc = request.data.get("title", ""), request.data.get("description", "")
        cat, kws = intelligence.suggest_category(f"{title} {desc}")
        sid = request.data.get("service")
        hits = intelligence.find_similar(title, desc, int(sid) if sid else None, threshold=0.4) if (title or desc) else []
        return Response({"category": CategorySerializer(cat).data if cat else None, "matched": kws,
                         "duplicates": [{"number": i.number, "title": i.title, "status": i.status, "score": s} for i, s in hits]})


# ---------------------------------------------------------------- configuration (admin write, everyone read)
class CategoryViewSet(viewsets.ModelViewSet):
    queryset, serializer_class, permission_classes = Category.objects.all(), CategorySerializer, [IsAdminOrReadOnly]


class ServiceViewSet(viewsets.ModelViewSet):
    queryset, serializer_class, permission_classes = Service.objects.all(), ServiceSerializer, [IsAdminOrReadOnly]


class SLAPolicyViewSet(viewsets.ModelViewSet):
    queryset = SLAPolicy.objects.select_related("service").order_by("service_id", "priority")
    serializer_class, permission_classes = SLAPolicySerializer, [IsAdminOrReadOnly]


class UserViewSet(viewsets.ModelViewSet):
    queryset, serializer_class, permission_classes = User.objects.all().order_by("role", "username"), UserAdminSerializer, [IsAdmin]

    def destroy(self, request, *args, **kwargs):          # soft-delete keeps history intact
        u = self.get_object()
        u.is_active = False
        u.save(update_fields=["is_active"])
        return Response(status=204)


@api_view(["GET"])
def technicians(request):
    if request.user.role != "ADMIN":
        raise UnauthorizedOperation("Administrators only.")
    return Response(UserSerializer(technician_pool(), many=True).data)


@api_view(["GET", "PATCH"])
def settings_view(request):
    s = SystemSetting.load()
    if request.method == "PATCH":
        if request.user.role != "ADMIN":
            raise UnauthorizedOperation("Administrators only.")
        ser = SettingSerializer(s, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
    return Response(SettingSerializer(s).data)


# ---------------------------------------------------------------- notifications / audit / reports / SLA
class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        qs = Notification.objects.filter(recipient=self.request.user).select_related("incident")
        ch = self.request.query_params.get("channel")
        return qs.filter(channel=ch) if ch else qs

    @action(detail=False, methods=["post"], url_path="mark-read")
    def mark_read(self, request):
        Notification.objects.filter(recipient=request.user, channel="IN_APP", is_read=False).update(is_read=True)
        return Response({"ok": True})

    @action(detail=False, methods=["get"])
    def unread(self, request):
        return Response({"count": Notification.objects.filter(recipient=request.user, channel="IN_APP", is_read=False).count()})


class AuditViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class, permission_classes = AuditSerializer, [IsAdmin]

    def get_queryset(self):
        qs = AuditLog.objects.select_related("user", "incident").order_by("-timestamp", "-id")
        if self.request.query_params.get("incident"):
            qs = qs.filter(incident__number=self.request.query_params["incident"])
        return qs[:500]


class SLACheckView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request):
        return Response(sla.check_all())


class ReportView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        qs = Incident.objects.all()
        open_qs = qs.exclude(status__in=DONE_STATUSES)
        resolved = qs.filter(resolved_at__isnull=False)
        mins = [(i.resolved_at - i.created_at).total_seconds() / 60 for i in resolved]
        count = lambda field: list(qs.values(label=F(field)).annotate(count=Count("id")).order_by("-count"))
        return Response({
            "overview": {
                "total": qs.count(), "open": open_qs.count(), "critical": open_qs.filter(priority="P1").count(),
                "resolved": qs.filter(status__in=DONE_STATUSES).count(),
                "sla_violations": qs.filter(Q(response_breached=True) | Q(resolution_breached=True)).count(),
                "escalated": qs.filter(escalation_level__gt=0).count(),
                "duplicates": qs.filter(duplicate_of__isnull=False).count(),
                "avg_resolution_minutes": round(sum(mins) / len(mins), 1) if mins else None,
                "avg_feedback": qs.aggregate(a=Avg("feedback_rating"))["a"],
            },
            "by_status": count("status"), "by_priority": count("priority"),
            "by_service": count("service__name"), "by_category": count("category__name"),
            "technician_workload": [{"id": t.id, "name": t.display_name, "active": t.load_count, "max_load": t.max_load,
                                     "available": t.is_available} for t in technician_pool()],
            "correlations": intelligence.correlate(),
        })

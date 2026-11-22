from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("incidents", views.IncidentViewSet, basename="incident")
router.register("categories", views.CategoryViewSet)
router.register("services", views.ServiceViewSet)
router.register("sla-policies", views.SlaPolicyViewSet)
router.register("dependencies", views.ServiceDependencyViewSet)
router.register("users", views.UserViewSet)
router.register("notifications", views.NotificationViewSet, basename="notification")
router.register("audit-events", views.AuditEventViewSet, basename="audit-event")

urlpatterns = [
    path("auth/login/", views.LoginView.as_view()),
    path("auth/logout/", views.LogoutView.as_view()),
    path("auth/me/", views.MeView.as_view()),
    path("technicians/", views.TechnicianWorkloadView.as_view()),
    path("settings/", views.SystemSettingsView.as_view()),
    path("reports/", views.ReportView.as_view()),
    path("situation/", views.SituationView.as_view()),
    path("service-map/", views.ServiceMapView.as_view()),
    path("sla/check/", views.SlaCheckView.as_view()),
    path("", include(router.urls)),
]

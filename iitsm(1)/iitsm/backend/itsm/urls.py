from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("incidents", views.IncidentViewSet, basename="incident")
router.register("categories", views.CategoryViewSet)
router.register("services", views.ServiceViewSet)
router.register("sla-policies", views.SLAPolicyViewSet)
router.register("users", views.UserViewSet)
router.register("notifications", views.NotificationViewSet, basename="notification")
router.register("audit", views.AuditViewSet, basename="audit")

urlpatterns = [
    path("auth/login/", views.login),
    path("auth/register/", views.register),
    path("auth/me/", views.me),
    path("auth/availability/", views.toggle_availability),
    path("technicians/", views.technicians),
    path("settings/", views.settings_view),
    path("reports/", views.ReportView.as_view()),
    path("sla/check/", views.SLACheckView.as_view()),
    path("", include(router.urls)),
]

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from . import models

admin.site.register(models.User, UserAdmin)
for model in (models.Category, models.Service, models.ServiceDependency, models.SlaPolicy, models.Incident,
              models.IncidentComment, models.AuditEvent, models.Notification, models.SystemConfiguration):
    admin.site.register(model)

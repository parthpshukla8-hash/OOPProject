from django.apps import AppConfig


class ItsmConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "itsm"

    def ready(self):
        # Observer pattern: register observers on the event bus.
        from .events import bus
        from .observers import AuditObserver, NotificationObserver
        bus.subscribe(AuditObserver())
        bus.subscribe(NotificationObserver())

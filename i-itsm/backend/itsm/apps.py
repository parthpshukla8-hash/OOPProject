from django.apps import AppConfig


class ItsmConfig(AppConfig):
    name = "itsm"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from .observers import register_default_observers
        register_default_observers()

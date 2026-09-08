"""Django application configuration."""

from django.apps import AppConfig


class StudioConfig(AppConfig):
    default_auto_field: str = "django.db.models.BigAutoField"
    name: str = "studio"

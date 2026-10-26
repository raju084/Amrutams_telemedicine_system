"""
Notifications app config for Amrutam Telemedicine.
"""
from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.notifications'
    verbose_name = 'Notifications'

    def ready(self):
        """Connect Django signals to notification dispatch on app startup."""
        import apps.notifications.signals  # noqa: F401

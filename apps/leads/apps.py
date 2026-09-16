from django.apps import AppConfig


class LeadsConfig(AppConfig):
    name = "apps.leads"
    verbose_name = "Заявки"

    def ready(self) -> None:
        from . import signals  # noqa: F401

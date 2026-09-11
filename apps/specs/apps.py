from django.apps import AppConfig


class SpecsConfig(AppConfig):
    name = "apps.specs"
    verbose_name = "Характеристики техники"

    def ready(self) -> None:
        from . import signals  # noqa: F401

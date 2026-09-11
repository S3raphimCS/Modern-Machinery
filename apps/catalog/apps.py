from django.apps import AppConfig


class CatalogConfig(AppConfig):
    name = "apps.catalog"
    verbose_name = "Каталог техники"

    def ready(self) -> None:
        from . import signals  # noqa: F401

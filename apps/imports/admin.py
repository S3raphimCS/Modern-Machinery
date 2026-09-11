"""Админка импорта."""

from django.contrib import admin

from .models import ImportRun, SourcePage


@admin.register(ImportRun)
class ImportRunAdmin(admin.ModelAdmin):
    list_display = ["kind", "source", "status", "started_at", "finished_at"]
    list_filter = ["status", "source", "kind"]
    readonly_fields = ["source", "kind", "status", "started_at", "finished_at", "stats", "log"]

    def has_add_permission(self, request) -> bool:
        # Прогоны создаются командами импорта, а не руками.
        return False


@admin.register(SourcePage)
class SourcePageAdmin(admin.ModelAdmin):
    list_display = ["path", "page_type", "http_status", "is_migrated", "target_path"]
    list_filter = ["page_type", "is_migrated", "http_status"]
    list_editable = ["page_type", "is_migrated"]
    search_fields = ["url", "path", "title"]

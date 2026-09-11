"""Админка SEO-слоя."""

from django.contrib import admin

from .models import NotFoundLog, RedirectRule


@admin.register(RedirectRule)
class RedirectRuleAdmin(admin.ModelAdmin):
    list_display = [
        "old_path",
        "new_path",
        "status_code",
        "hits",
        "last_hit_at",
        "is_auto",
        "is_active",
    ]
    list_filter = ["is_active", "is_auto", "status_code"]
    list_editable = ["is_active"]
    search_fields = ["old_path", "new_path", "note"]


@admin.register(NotFoundLog)
class NotFoundLogAdmin(admin.ModelAdmin):
    """Рабочий цикл после переезда: сортируем по числу обращений, заводим
    редирект, помечаем обработанным."""

    list_display = ["path", "hits", "referrer", "last_seen", "is_resolved"]
    list_filter = ["is_resolved"]
    list_editable = ["is_resolved"]
    search_fields = ["path", "referrer"]
    actions = ["mark_resolved"]

    @admin.action(description="Отметить обработанными")
    def mark_resolved(self, request, queryset):
        updated = queryset.update(is_resolved=True)
        self.message_user(request, f"Обработано: {updated}")

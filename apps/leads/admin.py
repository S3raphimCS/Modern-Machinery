"""Админка заявок.

Заявки — рабочий инструмент менеджера, поэтому список сделан как воронка:
фильтры по статусу и типу, быстрые действия и история событий прямо в карточке.
"""

from django.contrib import admin
from django.utils import timezone

from .models import ConsentVersion, Lead, LeadEvent, LeadRoutingRule


class LeadEventInline(admin.TabularInline):
    model = LeadEvent
    extra = 0
    fields = ["kind", "comment", "author", "created_at"]
    readonly_fields = ["created_at"]


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = [
        "created_at",
        "type",
        "name",
        "phone",
        "subject_title",
        "department",
        "status",
        "assigned_to",
    ]
    list_filter = ["status", "type", "department", "is_anonymized", "created_at"]
    list_editable = ["status", "assigned_to"]
    search_fields = ["name", "phone", "email", "company", "message"]
    date_hierarchy = "created_at"
    inlines = [LeadEventInline]
    autocomplete_fields = ["machine", "part", "service"]
    actions = ["mark_in_progress", "mark_done", "mark_spam"]
    readonly_fields = [
        "created_at",
        "updated_at",
        "source_url",
        "referrer",
        "utm",
        "ip_address",
        "user_agent",
        "consent",
        "consent_at",
        "purge_after",
        "is_anonymized",
    ]
    fieldsets = [
        (None, {"fields": ["type", "status", "assigned_to", "department", "processed_at"]}),
        ("Контакт", {"fields": ["name", "company", "inn", "phone", "email", "message"]}),
        ("Предмет заявки", {"fields": ["machine", "part", "service", "branch", "payload"]}),
        (
            "Источник",
            {
                "fields": ["source_url", "referrer", "utm", "ip_address", "user_agent"],
                "classes": ["collapse"],
            },
        ),
        (
            "Персональные данные",
            {
                "fields": ["consent", "consent_at", "purge_after", "is_anonymized"],
                "description": "Срок хранения ПДн и версия согласия — требование 152-ФЗ.",
                "classes": ["collapse"],
            },
        ),
        ("Даты", {"fields": ["created_at", "updated_at"], "classes": ["collapse"]}),
    ]

    def _set_status(self, request, queryset, status: str, label: str) -> None:
        for lead in queryset:
            lead.status = status
            if status in {Lead.Status.DONE, Lead.Status.SPAM}:
                lead.processed_at = timezone.now()
            lead.save(update_fields=["status", "processed_at", "updated_at"])
            LeadEvent.objects.create(
                lead=lead,
                kind=LeadEvent.Kind.STATUS_CHANGED,
                comment=f"Статус изменён на «{label}»",
                author=request.user,
            )
        self.message_user(request, f"Обновлено заявок: {queryset.count()}")

    @admin.action(description="Взять в работу")
    def mark_in_progress(self, request, queryset):
        self._set_status(request, queryset, Lead.Status.IN_PROGRESS, "В работе")

    @admin.action(description="Отметить обработанными")
    def mark_done(self, request, queryset):
        self._set_status(request, queryset, Lead.Status.DONE, "Обработана")

    @admin.action(description="Отметить спамом")
    def mark_spam(self, request, queryset):
        self._set_status(request, queryset, Lead.Status.SPAM, "Спам")


@admin.register(LeadRoutingRule)
class LeadRoutingRuleAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "lead_type",
        "machine_type",
        "category",
        "department",
        "priority",
        "is_active",
    ]
    list_filter = ["is_active", "lead_type", "department"]
    list_editable = ["priority", "is_active"]
    search_fields = ["name"]


@admin.register(ConsentVersion)
class ConsentVersionAdmin(admin.ModelAdmin):
    list_display = ["code", "version", "published_at", "is_active"]
    list_filter = ["code", "is_active"]
    search_fields = ["code", "version"]

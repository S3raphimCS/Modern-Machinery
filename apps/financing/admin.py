"""Админка раздела финансирования."""

from django.contrib import admin

from .models import LeasingPartner, LeasingTerms


@admin.register(LeasingPartner)
class LeasingPartnerAdmin(admin.ModelAdmin):
    list_display = ["name", "note", "is_active", "sort_order"]
    list_filter = ["is_active"]
    list_editable = ["is_active", "sort_order"]
    search_fields = ["name", "note"]


@admin.register(LeasingTerms)
class LeasingTermsAdmin(admin.ModelAdmin):
    list_display = ["__str__", "min_advance_percent", "max_months", "default_markup_percent"]
    fieldsets = [
        (
            "Условия",
            {
                "fields": [
                    "min_advance_percent",
                    "max_advance_percent",
                    "min_months",
                    "max_months",
                    "decision_days",
                    "is_credit_available",
                ],
                "description": "Эти же значения задают границы полей калькулятора на сайте.",
            },
        ),
        (
            "Калькулятор",
            {
                "fields": ["default_markup_percent"],
                "description": "Ориентир для расчёта. Точную ставку называет "
                "лизинговая компания после рассмотрения заявки.",
            },
        ),
        ("Текст раздела", {"fields": ["intro"]}),
    ]

    def has_add_permission(self, request) -> bool:
        # Условия — синглтон: вторая запись сделала бы расчёт зависящим от
        # порядка выборки.
        return not LeasingTerms.objects.exists()

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

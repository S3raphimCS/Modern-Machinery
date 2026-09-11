"""Админка справочника характеристик."""

from django.contrib import admin

from .models import SpecGroup, SpecKey, SpecOption


class SpecOptionInline(admin.TabularInline):
    model = SpecOption
    extra = 1


@admin.register(SpecGroup)
class SpecGroupAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "sort_order"]
    list_editable = ["sort_order"]
    prepopulated_fields = {"code": ("name",)}
    search_fields = ["name", "code"]


@admin.register(SpecKey)
class SpecKeyAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "code",
        "group",
        "unit",
        "value_type",
        "is_filterable",
        "is_in_card",
        "sort_order",
    ]
    list_filter = ["group", "value_type", "is_filterable", "is_in_card"]
    list_editable = ["is_filterable", "is_in_card", "sort_order"]
    search_fields = ["name", "code", "aliases"]
    prepopulated_fields = {"code": ("name",)}
    filter_horizontal = ["machine_types"]
    inlines = [SpecOptionInline]
    fieldsets = [
        (None, {"fields": ["name", "code", "group", "unit", "value_type", "decimals"]}),
        (
            "Поведение",
            {
                "fields": [
                    "is_filterable",
                    "is_in_card",
                    "is_comparable",
                    "sort_order",
                    "machine_types",
                ]
            },
        ),
        (
            "Импорт",
            {
                "fields": ["aliases"],
                "description": "Синонимы названия параметра из внешних источников. "
                "По ним импорт сам находит нужный параметр.",
            },
        ),
    ]

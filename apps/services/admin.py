"""Админка модуля услуг."""

from django.contrib import admin

from .models import Service, ServiceCategory


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "sort_order"]
    list_editable = ["sort_order"]
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name"]


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "category",
        "price_from",
        "is_on_site",
        "is_available",
        "is_published",
        "sort_order",
    ]
    list_filter = ["category", "is_on_site", "is_available", "is_published"]
    list_editable = ["is_published", "sort_order"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ["machine_types", "brands"]
    fieldsets = [
        (None, {"fields": ["name", "slug", "category", "short_description", "description"]}),
        (
            "Условия",
            {"fields": ["price_from", "price_note", "lead_time", "is_on_site", "is_available"]},
        ),
        ("Применимость", {"fields": ["machine_types", "brands"]}),
        ("Публикация", {"fields": ["is_published", "published_at", "sort_order"]}),
        (
            "SEO",
            {
                "fields": ["seo_title", "seo_description", "seo_h1", "og_image", "is_noindex"],
                "classes": ["collapse"],
            },
        ),
    ]

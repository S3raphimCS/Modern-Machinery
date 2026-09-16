"""Админка каталога техники."""

from django.contrib import admin
from django.utils.html import format_html
from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from apps.specs.models import MachineSpec

from .models import (
    Brand,
    CatalogLanding,
    CatalogLandingSpec,
    Category,
    Machine,
    MachineDocument,
    MachineImage,
    MachineStock,
    MachineType,
)


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_active", "sort_order", "machines_count"]
    list_filter = ["is_active"]
    list_editable = ["sort_order", "is_active"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = [
        (None, {"fields": ["name", "slug", "description", "is_active", "sort_order"]}),
        ("Изображения", {"fields": ["logo", "logo_hover"]}),
        (
            "SEO",
            {
                "fields": ["seo_title", "seo_description", "seo_h1", "og_image", "is_noindex"],
                "classes": ["collapse"],
            },
        ),
    ]

    @admin.display(description="Моделей")
    def machines_count(self, obj: Brand) -> int:
        return obj.machines.count()


class CatalogLandingSpecInline(admin.TabularInline):
    model = CatalogLandingSpec
    extra = 1
    autocomplete_fields = ["spec_key"]
    verbose_name = "условие по характеристике"
    verbose_name_plural = "Условия по характеристикам"


@admin.register(CatalogLanding)
class CatalogLandingAdmin(admin.ModelAdmin):
    inlines = [CatalogLandingSpecInline]
    list_display = [
        "title",
        "slug",
        "brand",
        "machine_type",
        "category",
        "is_published",
        "is_featured",
        "sort_order",
    ]
    list_filter = ["is_published", "is_featured", "brand", "machine_type"]
    list_editable = ["is_published", "is_featured", "sort_order"]
    search_fields = ["title", "slug", "intro"]
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ["brand", "machine_type"]
    fieldsets = [
        (
            None,
            {
                "fields": ["title", "slug", "intro"],
                "description": "Текст подборки должен быть уникальным. Копировать "
                "описания с корпоративного сайта нельзя: прямые дубли "
                "на одном домене понижают в выдаче обе страницы.",
            },
        ),
        (
            "Условия отбора",
            {
                "fields": ["brand", "machine_type", "category"],
                "description": "Хотя бы одно условие обязательно, иначе подборка "
                "повторит каталог целиком.",
            },
        ),
        ("Публикация", {"fields": ["is_published", "published_at", "is_featured", "sort_order"]}),
        (
            "SEO",
            {
                "fields": ["seo_title", "seo_description", "seo_h1", "og_image", "is_noindex"],
                "classes": ["collapse"],
            },
        ),
    ]


@admin.register(Category)
class CategoryAdmin(TreeAdmin):
    form = movenodeform_factory(Category)
    list_display = ["name", "slug", "is_active"]
    search_fields = ["name", "slug"]


@admin.register(MachineType)
class MachineTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "name_plural", "slug", "sort_order"]
    list_editable = ["sort_order"]
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name"]


class MachineImageInline(admin.TabularInline):
    model = MachineImage
    extra = 1
    fields = ["image", "preview", "alt", "is_main", "sort_order"]
    readonly_fields = ["preview"]

    @admin.display(description="Просмотр")
    def preview(self, obj: MachineImage) -> str:
        if not obj.pk or not obj.image:
            return "—"
        return format_html('<img src="{}" style="height:60px">', obj.thumbnail_url)


class MachineDocumentInline(admin.TabularInline):
    model = MachineDocument
    extra = 0
    fields = ["kind", "title", "file", "sort_order"]


class MachineSpecInline(admin.TabularInline):
    model = MachineSpec
    extra = 0
    fields = [
        "spec_key",
        "value_num",
        "value_num_max",
        "value_str",
        "value_bool",
        "value_option",
        "raw_value",
    ]
    autocomplete_fields = ["spec_key"]


class MachineStockInline(admin.TabularInline):
    model = MachineStock
    extra = 0
    fields = ["branch", "status", "quantity", "lead_time", "synced_at"]


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "brand",
        "machine_type",
        "is_published",
        "is_active",
        "is_featured",
        "sort_order",
    ]
    list_filter = ["is_published", "is_active", "is_featured", "brand", "machine_type"]
    list_editable = ["is_published", "is_featured", "sort_order"]
    search_fields = ["name", "full_name", "series", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ["brand", "machine_type"]
    filter_horizontal = ["categories"]
    inlines = [MachineImageInline, MachineSpecInline, MachineDocumentInline, MachineStockInline]
    readonly_fields = ["specs_cache", "created_at", "updated_at"]
    actions = ["publish", "unpublish"]
    fieldsets = [
        (
            None,
            {
                "fields": [
                    "name",
                    "full_name",
                    "slug",
                    "series",
                    "brand",
                    "machine_type",
                    "categories",
                ]
            },
        ),
        ("Тексты", {"fields": ["short_description", "description", "equipment", "warranty_note"]}),
        ("Цена", {"fields": ["price", "price_note", "is_price_on_request"]}),
        (
            "Публикация",
            {"fields": ["is_published", "published_at", "is_active", "is_featured", "sort_order"]},
        ),
        (
            "SEO",
            {
                "fields": ["seo_title", "seo_description", "seo_h1", "og_image", "is_noindex"],
                "classes": ["collapse"],
            },
        ),
        (
            "Служебное",
            {
                "fields": [
                    "specs_cache",
                    "raw_specs",
                    "source_url",
                    "source_hash",
                    "created_at",
                    "updated_at",
                ],
                "classes": ["collapse"],
            },
        ),
    ]

    @admin.action(description="Опубликовать выбранные")
    def publish(self, request, queryset):
        updated = 0
        for machine in queryset:
            machine.is_published = True
            machine.save(update_fields=["is_published"])
            updated += 1
        self.message_user(request, f"Опубликовано: {updated}")

    @admin.action(description="Снять с публикации")
    def unpublish(self, request, queryset):
        updated = 0
        for machine in queryset:
            machine.is_published = False
            machine.save(update_fields=["is_published"])
            updated += 1
        self.message_user(request, f"Снято с публикации: {updated}")

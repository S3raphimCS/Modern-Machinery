"""Админка каталога запчастей."""

from django.contrib import admin
from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from .models import Part, PartAnalog, PartApplicability, PartCategory, PartStock


@admin.register(PartCategory)
class PartCategoryAdmin(TreeAdmin):
    form = movenodeform_factory(PartCategory)
    list_display = ["name", "slug", "is_active"]
    search_fields = ["name", "slug"]


class PartApplicabilityInline(admin.TabularInline):
    model = PartApplicability
    extra = 1
    autocomplete_fields = ["machine"]


class PartAnalogInline(admin.TabularInline):
    model = PartAnalog
    fk_name = "part"
    extra = 0
    autocomplete_fields = ["analog"]


class PartStockInline(admin.TabularInline):
    model = PartStock
    extra = 0


@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ["article", "name", "brand", "category", "is_original", "is_published"]
    list_filter = ["is_published", "is_active", "is_original", "brand", "category"]
    search_fields = ["article", "article_norm", "name", "external_id"]
    autocomplete_fields = ["brand"]
    readonly_fields = ["article_norm", "created_at", "updated_at"]
    inlines = [PartApplicabilityInline, PartAnalogInline, PartStockInline]

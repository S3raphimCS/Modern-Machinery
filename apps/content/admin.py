"""Админка контента."""

from django.contrib import admin
from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from .models import MenuItem, NewsCategory, NewsPost, Page, PageBlock, SiteSettings, Vacancy


class PageBlockInline(admin.TabularInline):
    model = PageBlock
    extra = 0
    fields = ["block_type", "payload", "sort_order"]


@admin.register(Page)
class PageAdmin(TreeAdmin):
    form = movenodeform_factory(Page)
    list_display = ["title", "url_path", "is_published"]
    search_fields = ["title", "slug", "url_path"]
    inlines = [PageBlockInline]
    readonly_fields = ["url_path"]


@admin.register(NewsCategory)
class NewsCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name"]


@admin.register(NewsPost)
class NewsPostAdmin(admin.ModelAdmin):
    list_display = ["title", "published_at", "is_published"]
    list_filter = ["is_published", "categories"]
    list_editable = ["is_published"]
    search_fields = ["title", "excerpt", "body"]
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ["categories", "machines"]
    date_hierarchy = "published_at"


@admin.register(Vacancy)
class VacancyAdmin(admin.ModelAdmin):
    list_display = ["title", "branch", "department", "is_published"]
    list_filter = ["is_published", "department"]
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ["title", "description"]


@admin.register(MenuItem)
class MenuItemAdmin(TreeAdmin):
    form = movenodeform_factory(MenuItem)
    list_display = ["title", "location", "is_visible"]
    list_filter = ["location", "is_visible"]
    search_fields = ["title", "url"]


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ["__str__", "main_phone", "main_email"]

    def has_add_permission(self, request) -> bool:
        # Настройки — синглтон: вторая запись сделала бы поведение сайта
        # зависящим от порядка выборки.
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

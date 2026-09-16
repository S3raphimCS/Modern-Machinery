"""Админка контента."""

from django.contrib import admin
from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from .models import (
    MenuItem,
    NewsCategory,
    NewsPost,
    Page,
    PageBlock,
    Review,
    ReviewSource,
    SiteSettings,
    Vacancy,
)


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


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = [
        "author_name",
        "company",
        "rating",
        "machine",
        "service",
        "published_at",
        "is_published",
    ]
    list_filter = ["is_published", "rating", "machine__brand"]
    list_editable = ["is_published"]
    search_fields = ["author_name", "company", "text"]
    autocomplete_fields = ["machine", "service"]
    date_hierarchy = "published_at"
    fieldsets = [
        (
            "Автор",
            {
                "fields": ["author_name", "author_position", "company", "city"],
                "description": "Отзыв вносит менеджер со слов клиента и с его "
                "разрешения. Публичной формы нет: она принесла бы "
                "спам и чужие персональные данные.",
            },
        ),
        ("Отзыв", {"fields": ["rating", "text", "source_note"]}),
        (
            "Привязка",
            {
                "fields": ["machine", "service"],
                "description": "Привязанный к технике отзыв показывается на её "
                "карточке — и только там получает микроразметку.",
            },
        ),
        ("Публикация", {"fields": ["is_published", "published_at", "sort_order"]}),
    ]


@admin.register(ReviewSource)
class ReviewSourceAdmin(admin.ModelAdmin):
    list_display = ["platform", "rating", "reviews_count", "updated_at", "is_active"]
    list_editable = ["rating", "reviews_count", "is_active"]
    fieldsets = [
        (
            None,
            {
                "fields": ["platform", "rating", "reviews_count", "url", "is_active", "sort_order"],
                "description": "Цифры обновляются вручную: 2ГИС и Google не отдают "
                "отзывы через публичный API. Меняется такое раз в "
                "квартал.",
            },
        ),
        (
            "Виджет Яндекса",
            {
                "fields": ["widget_code"],
                "description": "Код виджета из Яндекс Карт: он сам подтягивает "
                "отзывы и обновляет их каждые 72 часа.",
                "classes": ["collapse"],
            },
        ),
    ]


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

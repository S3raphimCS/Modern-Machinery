"""Админка модуля компании."""

from django.contrib import admin

from .models import Branch, ContactPoint, Department, Employee


class BranchContactInline(admin.TabularInline):
    model = ContactPoint
    fk_name = "branch"
    extra = 1
    fields = ["kind", "value", "extension", "label", "sort_order"]


class EmployeeContactInline(admin.TabularInline):
    model = ContactPoint
    fk_name = "employee"
    extra = 1
    fields = ["kind", "value", "extension", "label", "sort_order"]


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ["city", "address", "is_head_office", "is_published"]
    prepopulated_fields = {"slug": ("city",)}
    search_fields = ["city", "address"]
    inlines = [BranchContactInline]
    fieldsets = [
        (None, {"fields": ["city", "slug", "address", "postcode", "is_head_office"]}),
        ("Карта и время", {"fields": ["latitude", "longitude", "timezone", "work_hours"]}),
        ("Описание", {"fields": ["description"]}),
        ("Публикация", {"fields": ["is_published", "published_at", "sort_order"]}),
        (
            "SEO",
            {
                "fields": ["seo_title", "seo_description", "seo_h1", "og_image", "is_noindex"],
                "classes": ["collapse"],
            },
        ),
    ]


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "sort_order"]
    list_editable = ["sort_order"]
    prepopulated_fields = {"code": ("name",)}
    search_fields = ["name", "code"]


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ["full_name", "position", "department", "branch", "is_published"]
    list_filter = ["branch", "department", "is_published"]
    search_fields = ["full_name", "position", "email"]
    inlines = [EmployeeContactInline]

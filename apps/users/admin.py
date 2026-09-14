from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = [
        "username",
        "email",
        "get_full_name",
        "department",
        "receives_lead_emails",
        "is_staff",
    ]
    list_filter = ["receives_lead_emails", "is_staff", "is_superuser", "is_active", "department"]
    search_fields = ["username", "email", "first_name", "last_name"]
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Личные данные", {"fields": ("first_name", "last_name", "email", "phone", "position")}),
        (
            "Работа",
            {
                "fields": ("department", "receives_lead_emails"),
                "description": "Получатель заявок обязан иметь адрес почты: "
                "иначе письмо отправить некуда, а галочка "
                "выглядит рабочей.",
            },
        ),
        (
            "Права",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Даты", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email", "password1", "password2"),
            },
        ),
    )

    @admin.display(description="ФИО")
    def get_full_name(self, obj: User) -> str:
        return obj.get_full_name()

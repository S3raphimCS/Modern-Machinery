"""Маршруты модуля компании."""

from django.urls import path

from . import views

app_name = "company"

urlpatterns = [
    path("", views.DeliveryView.as_view(), name="delivery"),
]

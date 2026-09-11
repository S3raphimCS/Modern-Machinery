"""Маршруты каталога запчастей."""

from django.urls import path

from . import views

app_name = "parts"

urlpatterns = [
    path("", views.PartListView.as_view(), name="part-list"),
    path("<int:pk>/", views.PartDetailView.as_view(), name="part-detail"),
]

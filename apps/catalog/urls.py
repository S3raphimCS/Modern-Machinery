"""Маршруты каталога техники."""

from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "catalog"

urlpatterns = [
    # Каталог техники — главная страница сайта, как в макете.
    path("", views.MachineListView.as_view(), name="machine-list"),
    # Канонический адрес один; /tehnika/ ведёт на него, чтобы не плодить дубли.
    path("tehnika/", RedirectView.as_view(pattern_name="catalog:machine-list", permanent=True)),
    path("tehnika/poisk/", views.machine_search_suggest, name="machine-search-suggest"),
    # Объявлено до карточки: иначе «sravnenie» будет принято за slug машины.
    path("tehnika/sravnenie/", views.MachineCompareView.as_view(), name="machine-compare"),
    path("tehnika/<slug:slug>/", views.MachineDetailView.as_view(), name="machine-detail"),
    # Посадочные подборки под геозапросы: «экскаваторы Komatsu Хабаровск».
    path("katalog/<slug:slug>/", views.CatalogLandingView.as_view(), name="landing"),
]

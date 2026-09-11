"""Маршруты контентной части сайта."""

from django.urls import path, re_path

from . import views

app_name = "content"

urlpatterns = [
    path("o-kompanii/", views.AboutView.as_view(), name="about"),
    path("novosti/", views.NewsListView.as_view(), name="news-list"),
    path("novosti/<slug:slug>/", views.NewsDetailView.as_view(), name="news-detail"),
    path("vakansii/", views.VacancyListView.as_view(), name="vacancy-list"),
    path("vakansii/<slug:slug>/", views.VacancyDetailView.as_view(), name="vacancy-detail"),
    path("kalkulyator/", views.tco_calculator, name="tco"),
    path("politika-konfidencialnosti/", views.privacy_policy, name="privacy"),
    path("zayavka/forma/", views.lead_form_modal, name="lead-form-modal"),
    path("zayavka/<slug:lead_type>/", views.lead_create, name="lead-create"),
    # Произвольные страницы ищутся последними, чтобы не перехватывать
    # маршруты разделов выше.
    re_path(r"^(?P<path>[\w\-]+(?:/[\w\-]+)*)/$", views.PageDetailView.as_view(), name="page"),
]

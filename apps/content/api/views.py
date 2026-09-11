"""Эндпоинты контента."""

from rest_framework import mixins, viewsets

from apps.content.models import NewsPost, Page, Vacancy

from .serializers import NewsPostSerializer, PageSerializer, VacancySerializer


class PageViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Статические страницы сайта."""

    serializer_class = PageSerializer
    lookup_field = "slug"
    pagination_class = None

    def get_queryset(self):
        return Page.objects.filter(is_published=True).prefetch_related("blocks")


class NewsViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Новости филиала."""

    serializer_class = NewsPostSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return NewsPost.objects.visible().prefetch_related("categories")


class VacancyViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Вакансии филиала."""

    serializer_class = VacancySerializer
    lookup_field = "slug"

    def get_queryset(self):
        return Vacancy.objects.visible().select_related("branch", "department")

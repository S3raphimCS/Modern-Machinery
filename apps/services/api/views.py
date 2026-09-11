"""Эндпоинты модуля услуг."""

from rest_framework import mixins, viewsets

from apps.services.models import Service, ServiceCategory

from .serializers import ServiceCategorySerializer, ServiceSerializer


class ServiceCategoryViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Категории услуг сервисного центра."""

    queryset = ServiceCategory.objects.all()
    serializer_class = ServiceCategorySerializer
    lookup_field = "slug"
    pagination_class = None


class ServiceViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Услуги сервисного центра."""

    serializer_class = ServiceSerializer
    lookup_field = "slug"

    def get_queryset(self):
        queryset = Service.objects.visible().select_related("category")
        category = self.request.query_params.get("category")
        if category:
            queryset = queryset.filter(category__slug=category)
        if self.request.query_params.get("on_site") in {"1", "true", "yes"}:
            queryset = queryset.filter(is_on_site=True)
        return queryset

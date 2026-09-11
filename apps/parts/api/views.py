"""Эндпоинты каталога запчастей."""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, viewsets

from apps.parts.models import Part, PartCategory

from .serializers import PartCategorySerializer, PartDetailSerializer, PartListSerializer


class PartCategoryViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Категории запчастей."""

    queryset = PartCategory.objects.filter(is_active=True)
    serializer_class = PartCategorySerializer
    lookup_field = "slug"
    pagination_class = None


@extend_schema(
    parameters=[
        OpenApiParameter(
            "q",
            str,
            description="Поиск по названию или артикулу в любом написании: "
            "«600 311 3750», «600-311-3750» и «6003113750» равнозначны",
        ),
        OpenApiParameter("category", str, description="Slug категории"),
        OpenApiParameter("brand", str, description="Slug бренда"),
        OpenApiParameter("machine", str, description="Slug техники: только подходящие детали"),
    ]
)
class PartViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Каталог запчастей."""

    def get_queryset(self):
        queryset = Part.objects.visible().select_related("brand", "category")
        if self.action == "retrieve":
            return queryset.prefetch_related("stocks__branch", "applicability__machine")
        queryset = queryset.prefetch_related("stocks")
        params = self.request.query_params
        if params.get("q"):
            queryset = queryset.search(params["q"])
        if params.get("category"):
            queryset = queryset.filter(category__slug=params["category"])
        if params.get("brand"):
            queryset = queryset.filter(brand__slug=params["brand"])
        if params.get("machine"):
            queryset = queryset.filter(applicability__machine__slug=params["machine"])
        return queryset

    def get_serializer_class(self):
        return PartDetailSerializer if self.action == "retrieve" else PartListSerializer

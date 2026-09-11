"""Эндпоинты каталога техники."""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.catalog.models import Brand, Category, Machine, MachineType
from apps.catalog.services.facets import get_facets
from apps.catalog.services.filters import apply_filters, parse_filters

from .serializers import (
    BrandSerializer,
    CategorySerializer,
    MachineDetailSerializer,
    MachineListSerializer,
    MachineTypeSerializer,
)


class BrandViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Бренды, представленные в каталоге."""

    queryset = Brand.objects.visible()
    serializer_class = BrandSerializer
    lookup_field = "slug"


class CategoryViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Дерево категорий техники."""

    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    lookup_field = "slug"
    pagination_class = None


class MachineTypeViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Типы техники: экскаватор, погрузчик, каток."""

    queryset = MachineType.objects.all()
    serializer_class = MachineTypeSerializer
    lookup_field = "slug"
    pagination_class = None


@extend_schema(
    parameters=[
        OpenApiParameter("q", str, description="Поисковый запрос по названию и модели"),
        OpenApiParameter("brand", str, description="Slug бренда, можно повторять"),
        OpenApiParameter("type", str, description="Slug типа техники, можно повторять"),
        OpenApiParameter("category", str, description="Slug категории"),
        OpenApiParameter("in_stock", bool, description="Только позиции в наличии"),
        OpenApiParameter("sort", str, description="Сортировка: name, -name, price, -price, new"),
        OpenApiParameter(
            "spec_<код>_min",
            str,
            description="Нижняя граница числовой характеристики, например spec_engine_power_min",
        ),
        OpenApiParameter(
            "spec_<код>_max", str, description="Верхняя граница числовой характеристики"
        ),
    ]
)
class MachineViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Каталог техники с фасетными фильтрами и поиском."""

    lookup_field = "slug"
    filter_backends = []

    def get_queryset(self):
        queryset = Machine.objects.visible()
        if self.action == "retrieve":
            return queryset.with_detail_relations()
        queryset = queryset.with_listing_relations()
        filters = parse_filters(self.request.query_params)
        return apply_filters(queryset, filters)

    def get_serializer_class(self):
        return MachineDetailSerializer if self.action == "retrieve" else MachineListSerializer

    @extend_schema(
        description=(
            "Счётчики и диапазоны для панели фильтров. Результат кэшируется и "
            "сбрасывается при изменении каталога."
        ),
        responses=dict,
    )
    @action(detail=False, methods=["get"])
    def facets(self, request):
        # Фасеты считаются от тех же параметров, что и сама выдача: иначе
        # счётчики в клиенте разойдутся со списком.
        return Response(get_facets(parse_filters(request.query_params)))

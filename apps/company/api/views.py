"""Эндпоинты модуля компании."""

from rest_framework import mixins, viewsets

from apps.company.models import Branch

from .serializers import BranchSerializer


class BranchViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Филиалы с контактами и сотрудниками."""

    serializer_class = BranchSerializer
    lookup_field = "slug"
    pagination_class = None

    def get_queryset(self):
        return Branch.objects.filter(is_published=True).prefetch_related(
            "contacts", "employees__contacts", "employees__department"
        )

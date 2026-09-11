"""Фабрики каталога запчастей."""

import factory

from apps.catalog.factories import BrandFactory, MachineFactory
from apps.company.factories import BranchFactory

from .models import Part, PartApplicability, PartCategory, PartStock


class PartCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PartCategory
        django_get_or_create = ["slug"]

    slug = factory.Sequence(lambda n: f"part-category-{n}")
    name = factory.Sequence(lambda n: f"Категория запчастей {n}")
    is_active = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        return model_class.objects.add_root(kwargs)


class PartFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Part

    article = factory.Sequence(lambda n: f"600-311-{3750 + n}")
    name = factory.Sequence(lambda n: f"Фильтр топливный {n}")
    brand = factory.SubFactory(BrandFactory)
    category = factory.SubFactory(PartCategoryFactory)
    is_published = True
    is_active = True


class PartStockFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PartStock

    part = factory.SubFactory(PartFactory)
    branch = factory.SubFactory(BranchFactory)
    status = PartStock.Status.IN_STOCK
    quantity = 10


class PartApplicabilityFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PartApplicability

    part = factory.SubFactory(PartFactory)
    machine = factory.SubFactory(MachineFactory)

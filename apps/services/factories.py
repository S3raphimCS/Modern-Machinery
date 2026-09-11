"""Фабрики модуля услуг."""

from decimal import Decimal

import factory

from .models import Service, ServiceCategory


class ServiceCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ServiceCategory
        django_get_or_create = ["slug"]

    slug = factory.Sequence(lambda n: f"service-category-{n}")
    name = factory.Sequence(lambda n: f"Категория услуг {n}")


class ServiceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Service
        skip_postgeneration_save = True

    slug = factory.Sequence(lambda n: f"service-{n}")
    name = factory.Sequence(lambda n: f"Услуга {n}")
    category = factory.SubFactory(ServiceCategoryFactory)
    price_from = Decimal("18000.00")
    lead_time = "1–2 дня"
    is_published = True

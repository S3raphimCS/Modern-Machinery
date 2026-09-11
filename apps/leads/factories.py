"""Фабрики заявок."""

import factory
from django.utils import timezone

from apps.company.factories import DepartmentFactory

from .models import ConsentVersion, Lead, LeadRoutingRule


class ConsentVersionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ConsentVersion
        django_get_or_create = ["code", "version"]

    code = "lead-form"
    version = "1.0"
    text = "Согласие на обработку персональных данных."
    published_at = factory.LazyFunction(timezone.now)
    is_active = True


class LeadFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Lead

    type = Lead.Type.PRICE
    name = factory.Sequence(lambda n: f"Клиент {n}")
    phone = "+7 914 000-00-00"


class LeadRoutingRuleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LeadRoutingRule

    name = factory.Sequence(lambda n: f"Правило {n}")
    department = factory.SubFactory(DepartmentFactory)
    emails = ["sales@modernmachinery.ru"]
    priority = 100
    is_active = True

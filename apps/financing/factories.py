"""Фабрики раздела финансирования."""

import factory

from .models import LeasingPartner, LeasingTerms


class LeasingPartnerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LeasingPartner

    name = factory.Sequence(lambda n: f"Лизинговая компания {n}")
    is_active = True


class LeasingTermsFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LeasingTerms
        django_get_or_create = ["pk"]

    pk = 1
    min_advance_percent = 10
    max_advance_percent = 49
    min_months = 12
    max_months = 60
    default_markup_percent = 7

"""Фабрики справочника характеристик."""

import factory

from .models import SpecGroup, SpecKey, SpecOption


class SpecGroupFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SpecGroup
        django_get_or_create = ["code"]

    code = factory.Sequence(lambda n: f"group-{n}")
    name = factory.Sequence(lambda n: f"Группа {n}")


class SpecKeyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SpecKey
        django_get_or_create = ["code"]

    code = factory.Sequence(lambda n: f"spec-{n}")
    name = factory.Sequence(lambda n: f"Параметр {n}")
    group = factory.SubFactory(SpecGroupFactory)
    unit = "кВт"
    value_type = SpecKey.ValueType.NUMBER
    is_filterable = True
    is_in_card = True


class SpecOptionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SpecOption

    spec_key = factory.SubFactory(SpecKeyFactory, value_type=SpecKey.ValueType.OPTION)
    code = factory.Sequence(lambda n: f"option-{n}")
    name = factory.Sequence(lambda n: f"Значение {n}")

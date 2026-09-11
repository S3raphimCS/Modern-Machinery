"""Фабрики каталога техники."""

import factory

from apps.company.factories import BranchFactory

from .models import (
    Brand,
    Category,
    Machine,
    MachineDocument,
    MachineImage,
    MachineStock,
    MachineType,
)


class BrandFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Brand
        django_get_or_create = ["slug"]

    slug = factory.Sequence(lambda n: f"brand-{n}")
    name = factory.Sequence(lambda n: f"Бренд {n}")
    is_active = True


class MachineTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MachineType
        django_get_or_create = ["slug"]

    slug = factory.Sequence(lambda n: f"type-{n}")
    name = factory.Sequence(lambda n: f"Тип {n}")
    name_plural = factory.LazyAttribute(lambda o: f"{o.name}ы")


class CategoryFactory(factory.django.DjangoModelFactory):
    """Категория — узел дерева, поэтому создаётся через treebeard."""

    class Meta:
        model = Category
        django_get_or_create = ["slug"]

    slug = factory.Sequence(lambda n: f"category-{n}")
    name = factory.Sequence(lambda n: f"Категория {n}")
    is_active = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        return model_class.objects.add_root(kwargs)


class MachineFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Machine
        django_get_or_create = ["slug"]
        skip_postgeneration_save = True

    slug = factory.Sequence(lambda n: f"machine-{n}")
    name = factory.Sequence(lambda n: f"PC{n}00-8")
    full_name = factory.LazyAttribute(lambda o: f"Экскаватор {o.name}")
    brand = factory.SubFactory(BrandFactory)
    machine_type = factory.SubFactory(MachineTypeFactory)
    is_published = True
    is_active = True


class MachineImageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MachineImage

    machine = factory.SubFactory(MachineFactory)
    image = factory.django.ImageField(filename="machine.jpg")
    alt = "Фото техники"


class MachineDocumentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MachineDocument

    machine = factory.SubFactory(MachineFactory)
    title = "Брошюра"
    file = factory.django.FileField(filename="brochure.pdf")


class MachineStockFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MachineStock

    machine = factory.SubFactory(MachineFactory)
    branch = factory.SubFactory(BranchFactory)
    status = MachineStock.Status.IN_STOCK
    quantity = 2

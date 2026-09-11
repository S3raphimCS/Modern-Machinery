"""Фабрики модуля компании."""

import factory

from .models import Branch, ContactPoint, Department, Employee


class BranchFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Branch
        django_get_or_create = ["slug"]

    slug = "khabarovsk"
    city = "Хабаровск"
    address = "ул. Промышленная, 20"
    work_hours = "Пн–Сб 9:00–18:00"
    is_published = True


class DepartmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Department
        django_get_or_create = ["code"]

    code = factory.Sequence(lambda n: f"dept-{n}")
    name = factory.Sequence(lambda n: f"Отдел {n}")


class EmployeeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Employee

    branch = factory.SubFactory(BranchFactory)
    department = factory.SubFactory(DepartmentFactory)
    full_name = factory.Sequence(lambda n: f"Сотрудник {n}")
    position = "Менеджер"
    is_published = True


class BranchContactFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ContactPoint

    branch = factory.SubFactory(BranchFactory)
    employee = None
    kind = ContactPoint.Kind.PHONE
    value = "+7 (4212) 45-67-00"

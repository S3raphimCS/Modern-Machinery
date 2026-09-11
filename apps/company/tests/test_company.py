"""Тесты модуля компании."""

import pytest
from django.db import IntegrityError, transaction

from apps.company.factories import BranchContactFactory, EmployeeFactory
from apps.company.models import ContactPoint

pytestmark = pytest.mark.django_db


def test_branch_str_and_url(branch):
    assert str(branch) == "Хабаровск"
    assert branch.get_absolute_url() == "/o-kompanii/khabarovsk/"


def test_contact_belongs_to_branch_or_employee(branch):
    """Контакт без владельца непонятно где показывать, с двумя — тем более."""
    employee = EmployeeFactory(branch=branch)
    with pytest.raises(IntegrityError), transaction.atomic():
        ContactPoint.objects.create(
            branch=branch, employee=employee, kind=ContactPoint.Kind.PHONE, value="1"
        )


def test_contact_requires_owner():
    with pytest.raises(IntegrityError), transaction.atomic():
        ContactPoint.objects.create(kind=ContactPoint.Kind.PHONE, value="1")


def test_display_value_includes_extension(branch):
    contact = BranchContactFactory(branch=branch, value="+7 (4212) 45-67-24", extension="1954")
    assert contact.display_value == "+7 (4212) 45-67-24 доб. 1954"


def test_display_value_without_extension(branch):
    assert BranchContactFactory(branch=branch, value="+7 (4212) 45-67-00").display_value == (
        "+7 (4212) 45-67-00"
    )


def test_whatsapp_is_supported_contact_kind(branch):
    """Кнопка WhatsApp есть в макете, значит нужен и тип контакта."""
    contact = BranchContactFactory(
        branch=branch, kind=ContactPoint.Kind.WHATSAPP, value="+7 914 771-05-42"
    )
    assert contact.get_kind_display() == "WhatsApp"


def test_contact_str(branch):
    assert str(BranchContactFactory(branch=branch)).startswith("Телефон:")


def test_employee_str(branch):
    assert str(EmployeeFactory(branch=branch, full_name="Ковалёв А. С.")) == "Ковалёв А. С."


def test_department_str(department):
    assert str(department) == "Отдел продаж техники"


def test_api_branch_includes_contacts_and_employees(client, branch):
    employee = EmployeeFactory(branch=branch, full_name="Литвинов П. И.")
    BranchContactFactory(branch=branch)
    ContactPoint.objects.create(
        employee=employee, kind=ContactPoint.Kind.MOBILE, value="+7 914 543-21-09"
    )

    data = client.get("/api/v1/branches/").json()[0]

    assert data["city"] == "Хабаровск"
    assert data["contacts"][0]["kind"] == "phone"
    assert data["employees"][0]["full_name"] == "Литвинов П. И."
    assert data["employees"][0]["contacts"][0]["value"] == "+7 914 543-21-09"


def test_api_hides_unpublished_branch(client, branch):
    branch.is_published = False
    branch.save()
    assert client.get("/api/v1/branches/").json() == []


def test_api_hides_unpublished_employee(client, branch):
    EmployeeFactory(branch=branch, is_published=False)
    assert client.get("/api/v1/branches/").json()[0]["employees"] == []

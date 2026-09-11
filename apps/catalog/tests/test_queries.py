"""Тесты на число обращений к базе.

Оптимизация запросов легко теряется при следующей правке: достаточно убрать
`prefetch_related` или обратиться к связи в шаблоне, и листинг снова начнёт
делать запрос на каждую карточку. Эти тесты фиксируют порядок величины и
падают, когда N+1 возвращается.

Точные числа намеренно заданы с запасом: тест должен ловить регрессию, а не
ломаться от каждого добавленного справочника.
"""

import pytest
from django.urls import reverse

from apps.catalog.factories import MachineFactory, MachineImageFactory, MachineStockFactory
from apps.parts.factories import PartFactory, PartStockFactory
from apps.specs.models import MachineSpec

pytestmark = pytest.mark.django_db

CATALOG_QUERY_LIMIT = 25
DETAIL_QUERY_LIMIT = 25
PARTS_QUERY_LIMIT = 20


def make_machines(brand, machine_type, branch, power_key, count: int):
    for index in range(count):
        machine = MachineFactory(
            slug=f"query-machine-{index}",
            name=f"M{index}",
            brand=brand,
            machine_type=machine_type,
        )
        MachineSpec.objects.create(machine=machine, spec_key=power_key, value_num=100 + index)
        MachineStockFactory(machine=machine, branch=branch)
        MachineImageFactory(machine=machine, is_main=True)


def test_catalog_listing_does_not_scale_with_rows(
    client, brand, machine_type, branch, power_key, django_assert_max_num_queries
):
    """Число запросов не должно расти вместе с числом карточек."""
    make_machines(brand, machine_type, branch, power_key, 12)

    with django_assert_max_num_queries(CATALOG_QUERY_LIMIT):
        response = client.get(reverse("catalog:machine-list"))

    assert response.status_code == 200
    assert len(response.context["machines"]) == 12


def test_catalog_query_count_is_stable_for_more_rows(
    client, brand, machine_type, branch, power_key, django_assert_max_num_queries
):
    """Тот же лимит при вдвое большем числе позиций на странице.

    Это и есть проверка на N+1: если бы запросы шли на каждую карточку,
    удвоение выборки удвоило бы их число.
    """
    make_machines(brand, machine_type, branch, power_key, 24)

    with django_assert_max_num_queries(CATALOG_QUERY_LIMIT):
        client.get(reverse("catalog:machine-list"), {"page_size": 24})


def test_machine_detail_query_count(
    client, machine, branch, power_key, django_assert_max_num_queries
):
    MachineSpec.objects.create(machine=machine, spec_key=power_key, value_num=257)
    MachineStockFactory(machine=machine, branch=branch)
    MachineImageFactory(machine=machine, is_main=True)

    with django_assert_max_num_queries(DETAIL_QUERY_LIMIT):
        assert client.get(machine.get_absolute_url()).status_code == 200


def test_parts_listing_query_count(client, brand, branch, django_assert_max_num_queries):
    for index in range(15):
        part = PartFactory(article=f"600-311-{4000 + index}", brand=brand)
        PartStockFactory(part=part, branch=branch)

    with django_assert_max_num_queries(PARTS_QUERY_LIMIT):
        assert client.get(reverse("parts:part-list")).status_code == 200


def test_api_listing_query_count(
    client, brand, machine_type, branch, power_key, django_assert_max_num_queries
):
    make_machines(brand, machine_type, branch, power_key, 12)

    with django_assert_max_num_queries(10):
        response = client.get("/api/v1/machines/")

    assert response.json()["count"] == 12

"""Тесты публичного API каталога."""

import pytest

from apps.catalog.factories import MachineImageFactory, MachineStockFactory
from apps.specs.models import MachineSpec

pytestmark = pytest.mark.django_db


def test_machine_list_returns_published(client, machine_factory_set):
    response = client.get("/api/v1/machines/")
    assert response.status_code == 200
    assert response.json()["count"] == 3


def test_machine_list_respects_filters(client, machine_factory_set, power_key):
    response = client.get("/api/v1/machines/", {"spec_engine_power_min": 300})
    assert response.json()["count"] == 1


def test_machine_list_search(client, machine):
    from apps.catalog.signals import rebuild_search_vector

    rebuild_search_vector(machine.pk)
    assert client.get("/api/v1/machines/", {"q": "PC400"}).json()["count"] == 1


def test_machine_list_item_shape(client, machine, power_key, branch):
    MachineSpec.objects.create(machine=machine, spec_key=power_key, value_num=257)
    MachineStockFactory(machine=machine, branch=branch)
    MachineImageFactory(machine=machine, is_main=True)

    item = client.get("/api/v1/machines/").json()["results"][0]
    assert item["slug"] == machine.slug
    assert item["brand"] == "Komatsu"
    assert item["specs_cache"]["engine_power"]["value"] == "257"
    assert item["stock_status"] == "in_stock"
    assert item["main_image"].startswith("http")
    assert item["url"] == "/tehnika/komatsu-pc400-8/"


def test_machine_detail_includes_specs(client, machine, power_key):
    MachineSpec.objects.create(machine=machine, spec_key=power_key, value_num=257)
    data = client.get(f"/api/v1/machines/{machine.slug}/").json()

    assert data["specs"][0] == {
        "code": "engine_power",
        "name": "Мощность двигателя",
        "group": "Двигатель",
        "unit": "кВт",
        "value": "257",
    }


def test_stock_api_hides_exact_quantity(client, machine, branch):
    """Точные остатки склада наружу не отдаются — только статус."""
    MachineStockFactory(machine=machine, branch=branch, quantity=7)
    stock = client.get(f"/api/v1/machines/{machine.slug}/").json()["stocks"][0]

    assert stock["status"] == "in_stock"
    assert "quantity" not in stock


def test_unpublished_machine_not_in_api(client, machine):
    machine.is_published = False
    machine.save()
    assert client.get(f"/api/v1/machines/{machine.slug}/").status_code == 404


def test_facets_endpoint(client, machine_factory_set, power_key):
    data = client.get("/api/v1/machines/facets/").json()
    assert data["total"] == 3
    assert data["numeric"][0]["code"] == "engine_power"


def test_brands_endpoint(client, brand):
    assert client.get("/api/v1/brands/").json()["results"][0]["slug"] == "komatsu"


def test_categories_endpoint(client, category):
    assert client.get("/api/v1/categories/").json()[0]["slug"] == category.slug


def test_machine_types_endpoint(client, machine_type):
    assert client.get("/api/v1/machine-types/").json()[0]["slug"] == "ekskavator"


def test_api_is_read_only_for_catalog(client, machine):
    """Каталог доступен только на чтение: писать может лишь ручка заявок.

    Анонимный POST отклоняется правами доступа (403) раньше, чем проверкой
    метода, — это строже и тоже верно.
    """
    assert client.post("/api/v1/machines/", {}).status_code in {403, 405}


def test_openapi_schema_available(client):
    assert client.get("/api/schema/").status_code == 200

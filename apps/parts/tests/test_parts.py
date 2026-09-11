"""Тесты каталога запчастей.

Ключевая проверка — поиск по артикулу. Снабженец вводит его как придётся, и от
этого напрямую зависит конверсия раздела.
"""

import pytest
from django.db import IntegrityError, transaction

from apps.core.utils import normalize_article
from apps.parts.factories import (
    PartApplicabilityFactory,
    PartCategoryFactory,
    PartFactory,
    PartStockFactory,
)
from apps.parts.models import Part, PartAnalog, PartStock

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("600-311-3750", "6003113750"),
        ("600 311 3750", "6003113750"),
        ("6003113750", "6003113750"),
        ("07063-01210", "0706301210"),
        ("abc-123", "ABC123"),
    ],
)
def test_normalize_article(raw, expected):
    assert normalize_article(raw) == expected


def test_article_norm_filled_on_save(brand):
    """Нормализация в save(), а не только в импорте.

    Иначе позиция, заведённая руками в админке, не нашлась бы поиском.
    """
    part = PartFactory(article="600-311-3750", brand=brand)
    assert part.article_norm == "6003113750"


@pytest.mark.parametrize("query", ["600-311-3750", "600 311 3750", "6003113750", "3113750"])
def test_search_finds_article_in_any_spelling(brand, query):
    PartFactory(article="600-311-3750", brand=brand, name="Фильтр топливный")
    assert Part.objects.visible().search(query).count() == 1


def test_search_finds_by_name(brand):
    PartFactory(article="600-311-9999", brand=brand, name="Фильтр гидравлический")
    assert Part.objects.visible().search("гидравлич").count() == 1


def test_search_is_case_insensitive(brand):
    PartFactory(article="AB-100", brand=brand, name="Ремень приводной")
    assert Part.objects.visible().search("ab-100").count() == 1


def test_blank_search_returns_all(brand):
    PartFactory(brand=brand)
    assert Part.objects.visible().search("").count() == 1


def test_article_unique_per_brand(brand):
    PartFactory(article="600-311-3750", brand=brand)
    with pytest.raises(IntegrityError), transaction.atomic():
        PartFactory(article="600-311-3750", brand=brand)


def test_same_article_allowed_for_other_brand(brand):
    from apps.catalog.factories import BrandFactory

    PartFactory(article="600-311-3750", brand=brand)
    PartFactory(article="600-311-3750", brand=BrandFactory(slug="techking"))
    assert Part.objects.count() == 2


def test_unpublished_part_hidden(brand):
    PartFactory(brand=brand, is_published=False)
    assert Part.objects.visible().count() == 0


def test_stock_status_prefers_available(brand, branch):
    part = PartFactory(brand=brand)
    PartStockFactory(part=part, branch=branch, status=PartStock.Status.IN_STOCK)
    assert part.stock_status == "in_stock"


def test_stock_status_defaults_to_none(brand):
    assert PartFactory(brand=brand).stock_status == "none"


def test_analog_cannot_reference_itself(brand):
    """Запчасть не может быть аналогом самой себе."""
    part = PartFactory(brand=brand)
    with pytest.raises(IntegrityError), transaction.atomic():
        PartAnalog.objects.create(part=part, analog=part)


def test_applicability_unique(brand, machine):
    part = PartFactory(brand=brand)
    PartApplicabilityFactory(part=part, machine=machine)
    with pytest.raises(IntegrityError), transaction.atomic():
        PartApplicabilityFactory(part=part, machine=machine)


def test_part_str(brand):
    part = PartFactory(article="600-311-3750", name="Фильтр", brand=brand)
    assert str(part) == "600-311-3750 — Фильтр"


def test_category_absolute_url():
    category = PartCategoryFactory(slug="filtry")
    assert category.get_absolute_url() == "/zapchasti/?category=filtry"


def test_part_list_page(client, brand):
    PartFactory(brand=brand, name="Фильтр масляный")
    response = client.get("/zapchasti/")
    assert response.status_code == 200
    assert response.context["total"] == 1


def test_part_list_search_via_htmx(client, brand):
    PartFactory(article="600-311-3750", brand=brand)
    response = client.get("/zapchasti/", {"q": "600 311 3750"}, HTTP_HX_REQUEST="true")
    names = [t.name for t in response.templates]

    assert response.context["total"] == 1
    assert "parts/partials/part_results.html" in names
    assert "base.html" not in names


def test_part_list_filtered_by_category(client, brand):
    category = PartCategoryFactory(slug="filtry")
    PartFactory(brand=brand, category=category)
    PartFactory(brand=brand)
    assert client.get("/zapchasti/", {"category": "filtry"}).context["total"] == 1


def test_part_detail_page(client, brand, branch):
    part = PartFactory(brand=brand)
    PartStockFactory(part=part, branch=branch)
    response = client.get(part.get_absolute_url())

    assert response.status_code == 200
    assert response.context["lead_form"] is not None


def test_api_list_and_detail(client, brand, machine, branch):
    part = PartFactory(brand=brand, article="600-311-3750")
    PartStockFactory(part=part, branch=branch, quantity=17)
    PartApplicabilityFactory(part=part, machine=machine)

    assert client.get("/api/v1/parts/").json()["count"] == 1

    data = client.get(f"/api/v1/parts/{part.pk}/").json()
    assert data["article"] == "600-311-3750"
    assert data["machines"][0]["slug"] == machine.slug
    # Точное количество на складе публично не отдаётся.
    assert "quantity" not in data["stocks"][0]


def test_api_search_by_article(client, brand):
    PartFactory(article="600-311-3750", brand=brand)
    assert client.get("/api/v1/parts/", {"q": "6003113750"}).json()["count"] == 1


def test_api_filter_by_machine(client, brand, machine):
    part = PartFactory(brand=brand)
    PartApplicabilityFactory(part=part, machine=machine)
    PartFactory(brand=brand)

    assert client.get("/api/v1/parts/", {"machine": machine.slug}).json()["count"] == 1


def test_api_part_categories(client):
    PartCategoryFactory(slug="filtry", name="Фильтры")
    assert client.get("/api/v1/part-categories/").json()[0]["slug"] == "filtry"

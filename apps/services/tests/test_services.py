"""Тесты модуля услуг."""

from decimal import Decimal

import pytest

from apps.services.factories import ServiceCategoryFactory, ServiceFactory
from apps.services.models import Service

pytestmark = pytest.mark.django_db


def test_display_price_with_note():
    service = ServiceFactory(price_from=Decimal("18000"), price_note="за нормо-час")
    assert service.display_price == "от 18 000 ₽ за нормо-час"


def test_display_price_on_request():
    assert ServiceFactory(price_from=None).display_price == "По запросу"


def test_unpublished_service_hidden():
    ServiceFactory(is_published=False)
    assert Service.objects.visible().count() == 0


def test_absolute_url():
    service = ServiceFactory(slug="remont-gidravliki")
    assert service.get_absolute_url() == "/uslugi/remont-gidravliki/"


def test_service_list_page(client):
    ServiceFactory(name="Плановое ТО")
    response = client.get("/uslugi/")
    assert response.status_code == 200
    assert len(response.context["services"]) == 1


def test_service_list_filtered_by_category(client):
    category = ServiceCategoryFactory(slug="diagnostika")
    ServiceFactory(category=category)
    ServiceFactory()
    assert len(client.get("/uslugi/", {"category": "diagnostika"}).context["services"]) == 1


def test_service_detail_page(client):
    service = ServiceFactory(slug="analiz-masel")
    response = client.get(service.get_absolute_url())

    assert response.status_code == 200
    assert response.context["lead_form"] is not None


def test_unpublished_service_detail_404(client):
    service = ServiceFactory(is_published=False)
    assert client.get(service.get_absolute_url()).status_code == 404


def test_api_list(client):
    ServiceFactory(slug="to-komatsu", name="ТО Komatsu")
    data = client.get("/api/v1/services/").json()["results"][0]

    assert data["slug"] == "to-komatsu"
    assert data["display_price"].startswith("от")


def test_api_filter_on_site(client):
    ServiceFactory(is_on_site=True)
    ServiceFactory(is_on_site=False)
    assert client.get("/api/v1/services/", {"on_site": "1"}).json()["count"] == 1


def test_api_service_categories(client):
    ServiceCategoryFactory(slug="obuchenie", name="Обучение")
    assert client.get("/api/v1/service-categories/").json()[0]["slug"] == "obuchenie"


def test_category_str():
    assert str(ServiceCategoryFactory(name="Диагностика")) == "Диагностика"

"""Сквозная проверка публичных страниц на демонстрационных данных.

Тест намеренно идёт по всему сайту разом: он ловит поломки маршрутизации и
шаблонов, которые не видны в узких тестах отдельных представлений.
"""

import pytest
from django.core.management import call_command
from django.db import transaction

pytestmark = pytest.mark.django_db


@pytest.fixture(scope="module")
def demo_site(django_db_setup, django_db_blocker):
    """Демо-данные создаются один раз на модуль: наполнение небыстрое.

    Всё делается внутри транзакции, которая откатывается на выходе. Без отката
    записи остались бы в переиспользуемой тестовой базе и протекли бы в
    остальные тесты — там, где тест ожидает одну позицию, внезапно оказались бы
    сотни демонстрационных.
    """
    with django_db_blocker.unblock(), transaction.atomic():
        call_command("seed_demo", "--parts", 20, "--quiet", "--no-images")
        yield
        transaction.set_rollback(True)


@pytest.fixture
def urls(demo_site):
    from apps.catalog.models import Machine
    from apps.parts.models import Part
    from apps.services.models import Service

    machine = Machine.objects.visible().first()
    part = Part.objects.visible().first()
    service = Service.objects.visible().first()

    return [
        "/",
        "/?brand=komatsu",
        "/?spec_engine_power_min=150&spec_engine_power_max=400",
        "/?in_stock=1&sort=name",
        "/?page=2",
        "/tehnika/poisk/?q=PC",
        machine.get_absolute_url(),
        "/zapchasti/",
        f"/zapchasti/?q={part.article}",
        part.get_absolute_url(),
        "/uslugi/",
        service.get_absolute_url(),
        "/o-kompanii/",
        "/novosti/",
        "/vakansii/",
        "/kalkulyator/",
        "/politika-konfidencialnosti/",
        "/zayavka/forma/?type=price",
        "/sitemap.xml",
        "/robots.txt",
        "/healthz/",
        "/api/v1/machines/",
        "/api/v1/machines/facets/",
        "/api/v1/brands/",
        "/api/v1/parts/",
        "/api/v1/services/",
        "/api/v1/branches/",
        "/api/v1/news/",
        "/api/schema/",
    ]


def test_every_public_page_responds(client, urls):
    """Каждый адрес запрашивается ровно один раз.

    Условие в генераторе делало бы по два запроса на страницу и удваивало
    время самого медленного теста набора.
    """
    responses = [(url, client.get(url).status_code) for url in urls]
    failures = [item for item in responses if item[1] != 200]

    assert failures == []


def test_catalog_shows_machines_with_specs(client, demo_site):
    content = client.get("/").content.decode()
    assert "Каталог техники" in content
    assert "Мощность двигателя" in content


def test_machine_card_renders_specs_and_price(client, demo_site):
    from apps.catalog.models import Machine

    machine = Machine.objects.visible().first()
    content = client.get(machine.get_absolute_url()).content.decode()

    assert machine.name in content
    assert "Характеристики" in content
    assert "Оставить заявку" in content


def test_structured_data_present(client, demo_site):
    """Микроразметка — часть SEO-стратегии под региональные запросы."""
    content = client.get("/").content.decode()
    assert '"@type": "LocalBusiness"' in content


def test_product_structured_data(client, demo_site):
    from apps.catalog.models import Machine

    machine = Machine.objects.visible().first()
    content = client.get(machine.get_absolute_url()).content.decode()

    assert '"@type": "Product"' in content
    assert '"@type": "BreadcrumbList"' in content


def test_missing_page_returns_custom_404(client, demo_site):
    response = client.get("/takoy-stranicy-net/")
    assert response.status_code == 404
    assert "Страница не найдена" in response.content.decode()

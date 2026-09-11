"""Тесты поиска по каталогу: точного, по опечаткам и по транслитерации."""

import pytest

from apps.catalog.factories import BrandFactory, MachineFactory, MachineTypeFactory
from apps.catalog.models import Machine
from apps.catalog.signals import rebuild_search_vector

pytestmark = pytest.mark.django_db


@pytest.fixture
def catalog(db):
    komatsu = BrandFactory(slug="komatsu", name="Komatsu")
    bomag = BrandFactory(slug="bomag", name="BOMAG")
    excavator = MachineTypeFactory(slug="ekskavator", name="Экскаватор")
    roller = MachineTypeFactory(slug="katok", name="Дорожный каток")

    items = [
        MachineFactory(
            slug="komatsu-pc400-8",
            name="PC400-8",
            full_name="Экскаватор Komatsu PC400-8",
            brand=komatsu,
            machine_type=excavator,
        ),
        MachineFactory(
            slug="bomag-bw-213",
            name="BW 213 D-5",
            full_name="Дорожный каток BOMAG BW 213 D-5",
            brand=bomag,
            machine_type=roller,
        ),
    ]
    for item in items:
        rebuild_search_vector(item.pk)
    return items


def visible():
    return Machine.objects.visible()


def test_exact_model_search(catalog):
    assert [item.name for item in visible().search("PC400")] == ["PC400-8"]


def test_search_by_type_word(catalog):
    assert visible().search("экскаватор").count() == 1


@pytest.mark.parametrize("typo", ["экскаватр", "экскаватор", "экскваатор"])
def test_typos_still_find_the_machine(catalog, typo):
    """Название набирают в спешке с телефона — опечатки норма."""
    assert visible().search(typo).count() >= 1


def test_cyrillic_brand_finds_latin_one(catalog):
    """Бренды записаны латиницей, а ищут их и кириллицей."""
    result = visible().search("Коматсу")

    assert result.count() == 1
    assert result.first().brand.name == "Komatsu"


def test_cyrillic_brand_case_insensitive(catalog):
    assert visible().search("БОМАГ").count() == 1


def test_latin_brand_still_works(catalog):
    assert visible().search("komatsu").count() == 1


def test_nonsense_returns_nothing(catalog):
    """Запасные варианты не должны превращать поиск в «найдётся всё»."""
    assert visible().search("абырвалг").count() == 0


def test_blank_query_returns_everything(catalog):
    assert visible().search("   ").count() == 2


def test_fuzzy_threshold_is_respected(catalog):
    """Порог решает, насколько далеко от написания можно отойти.

    Точное слово даёт похожесть 1.0 при любом пороге, поэтому проверяется
    именно опечатка: при жёстком пороге она отсекается, при мягком находится.
    """
    assert visible().fuzzy_search("экскаватр", threshold=0.95).count() == 0
    assert visible().fuzzy_search("экскаватр", threshold=0.3).count() == 1


def test_search_suggest_throttled(client, catalog, settings):
    """Автодополнение стреляет на каждое нажатие клавиши — лимит обязателен."""
    settings.SEARCH_THROTTLE_RATE = "2/min"

    first = client.get("/tehnika/poisk/", {"q": "PC400"})
    second = client.get("/tehnika/poisk/", {"q": "PC400"})
    third = client.get("/tehnika/poisk/", {"q": "PC400"})

    assert len(first.context["suggestions"]) == 1
    assert len(second.context["suggestions"]) == 1
    # Отказ молчаливый: подсказка не критична, ошибка под полем ввода мешала бы.
    assert third.status_code == 200
    assert third.context["suggestions"] == []
